"""Accelerated replay-buffer working-set and throughput validation."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import gc
import os
import time

from maple_reporter.recorder.replay_buffer import ReplayBufferRecorder


class ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def working_set_bytes() -> int:
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    get_process_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    get_process_memory.restype = wintypes.BOOL
    process = get_current_process()
    if not get_process_memory(
        process, ctypes.byref(counters), counters.cb
    ):
        raise ctypes.WinError()
    return int(counters.WorkingSetSize)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--payload-kib", type=int, default=8)
    args = parser.parse_args()

    recorder = ReplayBufferRecorder()
    recorder._running = True
    recorder._buffer_seconds = 30
    batch_frames = 10 * 60 * args.fps
    total_frames = int(args.hours * 60 * 60 * args.fps)
    rss_samples: list[int] = []
    batch_times: list[float] = []
    index = 0

    while index < total_frames:
        stop = min(total_frames, index + batch_frames)
        started = time.perf_counter()
        while index < stop:
            payload = bytes([index % 251]) * (args.payload_kib * 1024)
            recorder._append_frame(index / args.fps, payload)
            index += 1
        batch_times.append(time.perf_counter() - started)
        gc.collect()
        rss_samples.append(working_set_bytes())

    rss_drift = max(rss_samples) - min(rss_samples)
    slowdown_ratio = batch_times[-1] / max(batch_times[0], 1e-9)
    mib = 1024 * 1024
    print(f"simulated_hours={index / args.fps / 3600:.2f}")
    print(f"retained_frames={len(recorder._frames)}")
    print(f"window_seconds={recorder._buffered_duration_locked():.2f}")
    print(f"working_set_first_mib={rss_samples[0] / mib:.2f}")
    print(f"working_set_final_mib={rss_samples[-1] / mib:.2f}")
    print(f"working_set_range_mib={rss_drift / mib:.2f}")
    print(f"first_batch_seconds={batch_times[0]:.4f}")
    print(f"last_batch_seconds={batch_times[-1]:.4f}")
    print(f"slowdown_ratio={slowdown_ratio:.3f}")

    frame_limit = (30 * args.fps) + 2
    if len(recorder._frames) > frame_limit:
        print(f"FAIL: retained frame count exceeds {frame_limit}")
        return 1
    if rss_drift > 16 * mib:
        print("FAIL: working-set range exceeded 16 MiB after warm-up")
        return 1
    if slowdown_ratio > 2.0:
        print("FAIL: final append batch took more than 2x the first batch")
        return 1
    print("PASS: replay buffer remained bounded without progressive slowdown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
