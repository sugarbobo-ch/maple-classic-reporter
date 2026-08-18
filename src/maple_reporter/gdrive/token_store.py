"""Protected local storage for the user's Google OAuth token.

Windows DPAPI encrypts the token for the current Windows user. It protects
the token at rest from other users and casual file disclosure, but it cannot
protect a token from malware already running as the same user.
"""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


DPAPI_HEADER = b"MAPLE-REPORTER-DPAPI\x00"
SECRET_DPAPI_HEADER = b"MAPLE-REPORTER-SECRET-DPAPI\x00"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class ProtectedTokenStoreError(RuntimeError):
    """Raised when a protected token cannot be read or written."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _make_blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _load_dpapi_libraries():
    try:
        crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    except AttributeError as error:
        raise ProtectedTokenStoreError(
            "Windows DPAPI is unavailable in this runtime."
        ) from error

    blob_pointer = ctypes.POINTER(_DataBlob)
    crypt32.CryptProtectData.argtypes = [
        blob_pointer,
        ctypes.c_wchar_p,
        blob_pointer,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        blob_pointer,
    ]
    crypt32.CryptProtectData.restype = ctypes.c_int
    crypt32.CryptUnprotectData.argtypes = [
        blob_pointer,
        ctypes.POINTER(ctypes.c_wchar_p),
        blob_pointer,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        blob_pointer,
    ]
    crypt32.CryptUnprotectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def _protect_with_dpapi(data: bytes) -> bytes:
    if os.name != "nt":
        # The application is Windows-only. This fallback keeps source-level
        # tests and diagnostics usable on other platforms without pretending
        # that the file is encrypted there.
        return data

    crypt32, kernel32 = _load_dpapi_libraries()
    input_blob, input_buffer = _make_blob(data)
    output_blob = _DataBlob()
    protected = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "Maple Classic Reporter OAuth token",
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not protected:
        error_code = ctypes.get_last_error()
        raise ProtectedTokenStoreError(
            f"Windows DPAPI encryption failed (error {error_code})."
        )

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
        # Keep the input buffer alive until CryptProtectData returns.
        del input_buffer


def _unprotect_with_dpapi(data: bytes) -> bytes:
    if os.name != "nt":
        return data

    crypt32, kernel32 = _load_dpapi_libraries()
    input_blob, input_buffer = _make_blob(data)
    output_blob = _DataBlob()
    description = ctypes.c_wchar_p()
    unprotected = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        ctypes.byref(description),
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not unprotected:
        error_code = ctypes.get_last_error()
        raise ProtectedTokenStoreError(
            f"Windows DPAPI decryption failed (error {error_code})."
        )

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
        if description:
            kernel32.LocalFree(ctypes.cast(description, ctypes.c_void_p))
        del input_buffer


class ProtectedTokenStore:
    """Read and write a token JSON payload protected at rest on Windows."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).expanduser()

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None

        raw = self.path.read_bytes()
        if os.name == "nt":
            if not raw.startswith(DPAPI_HEADER):
                raise ProtectedTokenStoreError(
                    "OAuth token is not in the protected format."
                )
            raw = _unprotect_with_dpapi(raw[len(DPAPI_HEADER) :])

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProtectedTokenStoreError("OAuth token is not valid JSON.") from error

        if not isinstance(payload, dict):
            raise ProtectedTokenStoreError("OAuth token JSON must be an object.")
        return payload

    def save(self, token_json: str | Mapping[str, Any]) -> None:
        if isinstance(token_json, str):
            raw = token_json.encode("utf-8")
        else:
            raw = json.dumps(token_json, ensure_ascii=False).encode("utf-8")

        protected = _protect_with_dpapi(raw)
        output = DPAPI_HEADER + protected if os.name == "nt" else protected
        self.path.parent.mkdir(parents=True, exist_ok=True)

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as stream:
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def delete(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class ProtectedSecretStore:
    """Store a single application secret encrypted for the current user.

    The production application is Windows-only, so secrets fail closed on
    other platforms instead of silently falling back to plaintext storage.
    ``ProtectedTokenStore`` retains its legacy cross-platform behavior for
    migration/tests; new API keys and webhook credentials use this class.
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).expanduser()

    def load(self) -> str | None:
        if not self.path.is_file():
            return None
        if os.name != "nt":
            raise ProtectedTokenStoreError(
                "Protected application secrets require Windows DPAPI."
            )

        raw = self.path.read_bytes()
        if not raw.startswith(SECRET_DPAPI_HEADER):
            raise ProtectedTokenStoreError(
                "Application secret is not in the protected format."
            )
        try:
            value = _unprotect_with_dpapi(raw[len(SECRET_DPAPI_HEADER) :]).decode(
                "utf-8"
            )
        except (UnicodeDecodeError, ProtectedTokenStoreError) as error:
            raise ProtectedTokenStoreError(
                "Application secret could not be decrypted."
            ) from error
        return value

    def save(self, value: str) -> None:
        if os.name != "nt":
            raise ProtectedTokenStoreError(
                "Protected application secrets require Windows DPAPI."
            )
        if not isinstance(value, str):
            raise TypeError("Protected application secrets must be strings.")

        protected = SECRET_DPAPI_HEADER + _protect_with_dpapi(value.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "wb") as stream:
                stream.write(protected)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def delete(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
