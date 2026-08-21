"""Small, dependency-light primitives shared by the updater and release tools."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from functools import total_ordering
from pathlib import PurePosixPath
from typing import Any

CURRENT_MANIFEST_SCHEMA = 1
_SEMVER = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


@total_ordering
@dataclass(frozen=True)
class SemVer:
    """SemVer comparison without bringing a package into the updater."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = _SEMVER.match(str(value).strip())
        if not match:
            raise ValueError(f"Invalid semantic version: {value!r}")
        pre = tuple(match.group("pre").split(".")) if match.group("pre") else ()
        return cls(int(match.group("major")), int(match.group("minor")), int(match.group("patch")), pre)

    @property
    def is_prerelease(self) -> bool:
        return bool(self.prerelease)

    def __str__(self) -> str:
        suffix = f"-{'.'.join(self.prerelease)}" if self.prerelease else ""
        return f"{self.major}.{self.minor}.{self.patch}{suffix}"

    def _cmp_key(self) -> tuple[Any, ...]:
        if not self.prerelease:
            return (self.major, self.minor, self.patch, 1)
        parts: list[tuple[int, Any]] = []
        for item in self.prerelease:
            if item.isdigit():
                parts.append((0, int(item)))
            else:
                parts.append((1, item))
        return (self.major, self.minor, self.patch, 0, tuple(parts))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._cmp_key() < other._cmp_key()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SemVer) and self._cmp_key() == other._cmp_key()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_file(path: os.PathLike[str] | str, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(value: str) -> str:
    """Return a safe slash-normalised bundle path or raise ValueError."""

    raw = str(value).replace("\\", "/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or raw.startswith("/") or ":" in raw.split("/", 1)[0]:
        raise ValueError(f"Unsafe update path: {value!r}")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe update path: {value!r}")
    return path.as_posix()


def verify_ed25519(payload: bytes, signature: str | bytes, public_key: str | bytes | None) -> bool:
    """Verify a base64 Ed25519 signature when a public key is configured.

    The dependency is already transitively present in the application through
    Google OAuth.  Keeping this optional makes source-mode tests and local
    development usable before the release public key is provisioned.
    """

    if not public_key:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        def decode(value: str | bytes) -> bytes:
            if isinstance(value, bytes):
                return value
            return base64.b64decode(value.encode("ascii"), validate=True)

        Ed25519PublicKey.from_public_bytes(decode(public_key)).verify(decode(signature), payload)
        return True
    except Exception:
        return False
