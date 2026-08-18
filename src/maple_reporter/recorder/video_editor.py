"""Video editing and segment trimming utilities using PyAV."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

import av
import numpy as np

LOGGER = logging.getLogger(__name__)


def get_video_duration(file_path: str) -> float:
    """Return the total duration in seconds of a media file."""
    if not os.path.exists(file_path):
        return 0.0
    try:
        with av.open(file_path) as container:
            if container.duration is not None and container.duration > 0:
                return float(container.duration) / float(av.time_base)
            for stream in container.streams.video:
                if stream.duration is not None and stream.time_base is not None:
                    return float(stream.duration * stream.time_base)
    except Exception as err:
        LOGGER.warning("Failed to get video duration for %s: %s", file_path, err)
    return 0.0


def cut_video_segment(
    input_path: str,
    cut_start_sec: float,
    cut_end_sec: float,
    output_path: str,
) -> bool:
    """
    Remove the segment between cut_start_sec and cut_end_sec from input video,
    and save the joined remaining parts to output_path.
    Preserves video frames and audio tracks accurately.
    """
    if not os.path.exists(input_path):
        LOGGER.error("Input file does not exist: %s", input_path)
        return False

    cut_start = max(0.0, float(cut_start_sec))
    cut_end = max(cut_start + 0.05, float(cut_end_sec))
    cut_duration = cut_end - cut_start

    try:
        with av.open(input_path) as in_container:
            v_streams = in_container.streams.video
            a_streams = in_container.streams.audio

            if not v_streams:
                LOGGER.error("No video stream found in %s", input_path)
                return False

            in_video = v_streams[0]
            in_audio = a_streams[0] if a_streams else None

            # Calculate total video duration
            total_dur = 0.0
            if in_container.duration:
                total_dur = float(in_container.duration) / float(av.time_base)
            elif in_video.duration and in_video.time_base:
                total_dur = float(in_video.duration * in_video.time_base)

            # Ensure cut range doesn't exceed total duration
            if total_dur > 0:
                cut_end = min(total_dur, cut_end)
                cut_duration = cut_end - cut_start

            # Open output container
            with av.open(output_path, mode="w", format="mp4") as out_container:
                fps = in_video.average_rate or in_video.guessed_rate or 30
                out_video = out_container.add_stream("libx264", rate=fps)
                out_video.width = in_video.width
                out_video.height = in_video.height
                out_video.pix_fmt = in_video.pix_fmt or "yuv420p"
                out_video.options = {"preset": "ultrafast", "crf": "22"}

                out_audio = None
                if in_audio:
                    try:
                        out_audio = out_container.add_stream("aac", rate=in_audio.sample_rate)
                        out_audio.layout = in_audio.layout.name if in_audio.layout else "stereo"
                        out_audio.format = "fltp"
                    except Exception as a_err:
                        LOGGER.warning("Could not setup audio stream for cut: %s", a_err)
                        out_audio = None

                # Video pass
                for frame in in_container.decode(video=0):
                    pts_time = float(frame.time) if frame.time is not None else 0.0

                    # Skip frames inside the cut zone
                    if cut_start <= pts_time <= cut_end:
                        continue

                    # Create fresh frame without stale input pts for seamless output pts generation
                    new_frame = av.VideoFrame.from_ndarray(frame.to_ndarray(format="yuv420p"), format="yuv420p")
                    for packet in out_video.encode(new_frame):
                        out_container.mux(packet)

                # Flush video encoder
                for packet in out_video.encode():
                    out_container.mux(packet)

                # Audio pass
                if in_audio and out_audio:
                    in_container.seek(0)
                    for frame in in_container.decode(audio=0):
                        pts_time = float(frame.time) if frame.time is not None else 0.0

                        if cut_start <= pts_time <= cut_end:
                            continue

                        # Clean audio frame pts
                        new_audio = av.AudioFrame.from_ndarray(
                            frame.to_ndarray(),
                            layout=frame.layout.name,
                            format=frame.format.name,
                        )
                        new_audio.sample_rate = frame.sample_rate
                        for packet in out_audio.encode(new_audio):
                            out_container.mux(packet)

                    # Flush audio encoder
                    for packet in out_audio.encode():
                        out_container.mux(packet)

        LOGGER.info(
            "Video cut successful: removed %.2f~%.2f sec (duration reduced by %.2f sec) -> %s",
            cut_start,
            cut_end,
            cut_duration,
            output_path,
        )
        return True

    except Exception as err:
        LOGGER.error("Failed to cut video segment: %s", err, exc_info=True)
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        return False


__all__ = ["get_video_duration", "cut_video_segment"]
