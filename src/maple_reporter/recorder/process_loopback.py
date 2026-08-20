"""Windows process-tree loopback capture built on the native WASAPI API.

The public ``soundcard`` package only exposes endpoint loopback capture.  This
module binds the newer ``ActivateAudioInterfaceAsync`` process-loopback path so
the recorder can capture one application process and its children without
including unrelated desktop audio.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import POINTER, Structure, Union, byref, cast
from ctypes import wintypes
from typing import Callable

import numpy as np


VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK = "VAD\\Process_Loopback"

_VT_BLOB = 65
_AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
_PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0

_AUDCLNT_SHAREMODE_SHARED = 0
_AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
_AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
_AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
_AUDCLNT_BUFFERFLAGS_SILENT = 0x00000002

_WAVE_FORMAT_PCM = 1
_COINIT_MULTITHREADED = 0x0
_S_OK = 0


class ProcessLoopbackUnavailable(RuntimeError):
    """Raised when Windows cannot create a process-scoped loopback stream."""


class _ProcessLoopbackParams(Structure):
    _fields_ = [
        ("TargetProcessId", wintypes.DWORD),
        ("ProcessLoopbackMode", ctypes.c_int),
    ]


class _ActivationUnion(Union):
    _fields_ = [("ProcessLoopbackParams", _ProcessLoopbackParams)]


class _AudioClientActivationParams(Structure):
    _anonymous_ = ("Options",)
    _fields_ = [("ActivationType", ctypes.c_int), ("Options", _ActivationUnion)]


class _Blob(Structure):
    _fields_ = [
        ("cbSize", wintypes.ULONG),
        ("pBlobData", POINTER(ctypes.c_ubyte)),
    ]


class _PropVariantValue(Union):
    _fields_ = [("blob", _Blob)]


class _PropVariant(Structure):
    _anonymous_ = ("value",)
    _fields_ = [
        ("vt", ctypes.c_ushort),
        ("wReserved1", ctypes.c_ushort),
        ("wReserved2", ctypes.c_ushort),
        ("wReserved3", ctypes.c_ushort),
        ("value", _PropVariantValue),
    ]


class _WaveFormatEx(Structure):
    _fields_ = [
        ("wFormatTag", ctypes.c_ushort),
        ("nChannels", ctypes.c_ushort),
        ("nSamplesPerSec", wintypes.DWORD),
        ("nAvgBytesPerSec", wintypes.DWORD),
        ("nBlockAlign", ctypes.c_ushort),
        ("wBitsPerSample", ctypes.c_ushort),
        ("cbSize", ctypes.c_ushort),
    ]


if os.name == "nt":
    from comtypes import COMMETHOD, COMObject, GUID, HRESULT, IUnknown

    class _IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
        _methods_: list = []

    class _IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
        _methods_: list = []

    class _IAgileObject(IUnknown):
        _iid_ = GUID("{94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90}")
        _methods_: list = []

    class _IAudioClient(IUnknown):
        _iid_ = GUID("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
        _methods_: list = []

    class _IAudioCaptureClient(IUnknown):
        _iid_ = GUID("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
        _methods_: list = []

    _IActivateAudioInterfaceAsyncOperation._methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "GetActivateResult",
            ([], POINTER(HRESULT), "activateResult"),
            ([], POINTER(POINTER(IUnknown)), "activatedInterface"),
        )
    ]
    _IActivateAudioInterfaceCompletionHandler._methods_ = [
        COMMETHOD(
            [],
            HRESULT,
            "ActivateCompleted",
            ([], POINTER(_IActivateAudioInterfaceAsyncOperation), "operation"),
        )
    ]
    _IAudioClient._methods_ = [
        COMMETHOD(
            [], HRESULT, "Initialize",
            ([], ctypes.c_int, "shareMode"),
            ([], wintypes.DWORD, "streamFlags"),
            ([], ctypes.c_longlong, "bufferDuration"),
            ([], ctypes.c_longlong, "periodicity"),
            ([], POINTER(_WaveFormatEx), "format"),
            ([], POINTER(GUID), "audioSessionGuid"),
        ),
        COMMETHOD([], HRESULT, "GetBufferSize", ([], POINTER(wintypes.UINT), "frames")),
        COMMETHOD([], HRESULT, "GetStreamLatency", ([], POINTER(ctypes.c_longlong), "latency")),
        COMMETHOD([], HRESULT, "GetCurrentPadding", ([], POINTER(wintypes.UINT), "padding")),
        COMMETHOD(
            [], HRESULT, "IsFormatSupported",
            ([], ctypes.c_int, "shareMode"),
            ([], POINTER(_WaveFormatEx), "format"),
            ([], POINTER(POINTER(_WaveFormatEx)), "closestMatch"),
        ),
        COMMETHOD([], HRESULT, "GetMixFormat", ([], POINTER(POINTER(_WaveFormatEx)), "format")),
        COMMETHOD(
            [], HRESULT, "GetDevicePeriod",
            ([], POINTER(ctypes.c_longlong), "defaultPeriod"),
            ([], POINTER(ctypes.c_longlong), "minimumPeriod"),
        ),
        COMMETHOD([], HRESULT, "Start"),
        COMMETHOD([], HRESULT, "Stop"),
        COMMETHOD([], HRESULT, "Reset"),
        COMMETHOD([], HRESULT, "SetEventHandle", ([], wintypes.HANDLE, "eventHandle")),
        COMMETHOD(
            [], HRESULT, "GetService",
            ([], POINTER(GUID), "serviceGuid"),
            ([], POINTER(ctypes.c_void_p), "service"),
        ),
    ]
    _IAudioCaptureClient._methods_ = [
        COMMETHOD(
            [], HRESULT, "GetBuffer",
            ([], POINTER(POINTER(ctypes.c_ubyte)), "data"),
            ([], POINTER(wintypes.UINT), "frames"),
            ([], POINTER(wintypes.DWORD), "flags"),
            ([], POINTER(ctypes.c_uint64), "devicePosition"),
            ([], POINTER(ctypes.c_uint64), "qpcPosition"),
        ),
        COMMETHOD([], HRESULT, "ReleaseBuffer", ([], wintypes.UINT, "frames")),
        COMMETHOD([], HRESULT, "GetNextPacketSize", ([], POINTER(wintypes.UINT), "frames")),
    ]

    class _ActivationHandler(COMObject):
        _com_interfaces_ = [_IActivateAudioInterfaceCompletionHandler, _IAgileObject]

        def __init__(self) -> None:
            super().__init__()
            self.completed = threading.Event()
            self.result: int | None = None
            self.audio_client = None
            self.error: Exception | None = None

        def ActivateCompleted(self, this, operation) -> int:  # noqa: N802 - COM name
            try:
                activate_result = HRESULT()
                activated = POINTER(IUnknown)()
                operation.GetActivateResult(byref(activate_result), byref(activated))
                self.result = int(activate_result.value)
                if self.result < 0:
                    raise ProcessLoopbackUnavailable(
                        f"Windows 無法啟用遊戲音訊擷取（0x{self.result & 0xFFFFFFFF:08X}）。"
                    )
                self.audio_client = activated.QueryInterface(_IAudioClient)
            except Exception as error:  # pragma: no cover - callback is OS-driven
                self.error = error
            finally:
                self.completed.set()
            return _S_OK


def is_process_loopback_supported() -> bool:
    """Return whether the current host exposes the process-loopback API."""

    if os.name != "nt":
        return False
    try:
        return hasattr(ctypes.WinDLL("Mmdevapi.dll"), "ActivateAudioInterfaceAsync")
    except OSError:
        return False


def _activate_process_audio_client(process_id: int):
    if os.name != "nt" or not is_process_loopback_supported():
        raise ProcessLoopbackUnavailable("目前的 Windows 版本不支援僅錄製遊戲聲音。")
    if int(process_id) <= 0:
        raise ProcessLoopbackUnavailable("找不到所選視窗的音訊程序，請重新整理視窗。")

    activation = _AudioClientActivationParams()
    activation.ActivationType = _AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK
    activation.ProcessLoopbackParams.TargetProcessId = int(process_id)
    activation.ProcessLoopbackParams.ProcessLoopbackMode = (
        _PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE
    )
    variant = _PropVariant()
    variant.vt = _VT_BLOB
    variant.blob.cbSize = ctypes.sizeof(activation)
    variant.blob.pBlobData = cast(byref(activation), POINTER(ctypes.c_ubyte))

    handler = _ActivationHandler()
    handler_interface = handler.QueryInterface(_IActivateAudioInterfaceCompletionHandler)
    operation = POINTER(_IActivateAudioInterfaceAsyncOperation)()
    mmdevapi = ctypes.WinDLL("Mmdevapi.dll")
    activate = mmdevapi.ActivateAudioInterfaceAsync
    activate.argtypes = [
        wintypes.LPCWSTR,
        POINTER(GUID),
        POINTER(_PropVariant),
        POINTER(_IActivateAudioInterfaceCompletionHandler),
        POINTER(POINTER(_IActivateAudioInterfaceAsyncOperation)),
    ]
    activate.restype = HRESULT
    result = int(
        activate(
            VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,
            byref(_IAudioClient._iid_),
            byref(variant),
            handler_interface,
            byref(operation),
        )
    )
    if result < 0:
        raise ProcessLoopbackUnavailable(
            f"Windows 無法啟用遊戲音訊擷取（0x{result & 0xFFFFFFFF:08X}）。"
        )
    if not handler.completed.wait(timeout=5.0):
        raise ProcessLoopbackUnavailable("等待遊戲音訊來源逾時，請重新選擇錄影視窗。")
    if handler.error:
        if isinstance(handler.error, ProcessLoopbackUnavailable):
            raise handler.error
        raise ProcessLoopbackUnavailable("無法開啟所選遊戲的音訊來源。") from handler.error
    if handler.audio_client is None:
        raise ProcessLoopbackUnavailable("所選遊戲目前沒有可用的音訊來源。")
    return handler.audio_client


def capture_process_audio(
    process_id: int,
    sample_rate: int,
    stop_event: threading.Event,
    on_chunk: Callable[[float, np.ndarray], None],
    on_opened: Callable[[], None],
) -> None:
    """Capture PCM from a process tree until ``stop_event`` is set."""

    if os.name != "nt":
        raise ProcessLoopbackUnavailable("僅錄製遊戲聲音只支援 Windows。")

    from comtypes import CoInitializeEx, CoUninitialize

    com_initialized = False
    try:
        CoInitializeEx(_COINIT_MULTITHREADED)
        com_initialized = True
    except OSError as error:
        # A host UI thread can already be initialized as STA.  The callback is
        # agile, so activation remains safe; only skip the matching uninitialize.
        if getattr(error, "winerror", None) != -2147417850:  # RPC_E_CHANGED_MODE
            raise
    audio_client = None
    capture_client = None
    started = False
    try:
        audio_client = _activate_process_audio_client(process_id)
        channels = 2
        bits_per_sample = 16
        block_align = channels * bits_per_sample // 8
        wave_format = _WaveFormatEx(
            wFormatTag=_WAVE_FORMAT_PCM,
            nChannels=channels,
            nSamplesPerSec=int(sample_rate),
            nAvgBytesPerSec=int(sample_rate) * block_align,
            nBlockAlign=block_align,
            wBitsPerSample=bits_per_sample,
            cbSize=0,
        )
        flags = (
            _AUDCLNT_STREAMFLAGS_LOOPBACK
            | _AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM
            | _AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY
        )
        audio_client.Initialize(
            _AUDCLNT_SHAREMODE_SHARED,
            flags,
            0,
            0,
            byref(wave_format),
            None,
        )
        service = ctypes.c_void_p()
        audio_client.GetService(byref(_IAudioCaptureClient._iid_), byref(service))
        capture_client = cast(service, POINTER(_IAudioCaptureClient))
        audio_client.Start()
        started = True
        on_opened()

        stream_anchor_time: float | None = None
        total_samples = 0
        while not stop_event.wait(0.01):
            packet_frames = wintypes.UINT()
            capture_client.GetNextPacketSize(byref(packet_frames))
            while packet_frames.value > 0:
                data = POINTER(ctypes.c_ubyte)()
                frames = wintypes.UINT()
                buffer_flags = wintypes.DWORD()
                device_position = ctypes.c_uint64()
                qpc_position = ctypes.c_uint64()
                capture_client.GetBuffer(
                    byref(data),
                    byref(frames),
                    byref(buffer_flags),
                    byref(device_position),
                    byref(qpc_position),
                )
                try:
                    frame_count = int(frames.value)
                    if frame_count > 0:
                        if buffer_flags.value & _AUDCLNT_BUFFERFLAGS_SILENT:
                            chunk = np.zeros((frame_count, channels), dtype=np.float32)
                        else:
                            byte_count = frame_count * block_align
                            pcm = ctypes.string_at(data, byte_count)
                            chunk = (
                                np.frombuffer(pcm, dtype="<i2")
                                .reshape(frame_count, channels)
                                .astype(np.float32)
                                / 32768.0
                            )
                        now = time.monotonic()
                        duration = frame_count / int(sample_rate)
                        if stream_anchor_time is None:
                            stream_anchor_time = now - duration
                            total_samples = 0
                        expected_start = stream_anchor_time + total_samples / int(sample_rate)
                        measured_start = now - duration
                        if abs(measured_start - expected_start) > 0.250:
                            stream_anchor_time = measured_start
                            total_samples = 0
                            chunk_start = measured_start
                        else:
                            chunk_start = expected_start
                        total_samples += frame_count
                        on_chunk(chunk_start, np.ascontiguousarray(chunk))
                finally:
                    capture_client.ReleaseBuffer(frames.value)
                capture_client.GetNextPacketSize(byref(packet_frames))
    except ProcessLoopbackUnavailable:
        raise
    except Exception as error:
        raise ProcessLoopbackUnavailable(
            "無法只錄製遊戲聲音。影片將繼續錄製但不包含聲音。"
        ) from error
    finally:
        if started and audio_client is not None:
            try:
                audio_client.Stop()
            except Exception:
                pass
        capture_client = None
        audio_client = None
        if com_initialized:
            CoUninitialize()


__all__ = [
    "ProcessLoopbackUnavailable",
    "capture_process_audio",
    "is_process_loopback_supported",
]
