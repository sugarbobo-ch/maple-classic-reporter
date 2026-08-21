"""File import, media streaming, preview, editing, and storage management."""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any

import webview

from maple_reporter.recorder.video_editor import cut_video_segment, get_video_duration
from maple_reporter.utils.config import get_recordings_dir

LOGGER = logging.getLogger(__name__)


class MediaBridgeMixin:
    """Methods for importing, previewing, streaming, trimming and deleting recorded media."""

    def select_local_file(self) -> str | None:
        """Open native file dialog to select image or video file."""
        if not getattr(self, "_window", None):
            return None
        file_types = (
            "Evidence files (*.mp4;*.png;*.jpg;*.jpeg;*.mkv;*.avi;*.mov)",
            "All files (*.*)",
        )
        result = self._window.create_file_dialog(
            getattr(webview.FileDialog, "OPEN", webview.OPEN_DIALOG),
            allow_multiple=False,
            file_types=file_types,
            directory=str(get_recordings_dir()),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def process_imported_file(self, file_path: str) -> dict[str, Any]:
        """Decode keyframes from an imported file and run OCR."""
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "message": "檔案不存在"}

        try:
            keyframes = self.capture_controller.load_keyframes(file_path)
            if not keyframes:
                return {"status": "error", "message": "無法解析媒體影格"}

            ext = Path(file_path).suffix.lower()
            media_type = "video" if ext in {".mp4", ".mkv", ".avi", ".mov"} else "image"
            ocr_res = self._perform_ocr(keyframes)
            if ocr_res.get("cancelled"):
                return {"status": "cancelled", "message": "辨識已取消"}

            return {
                "status": "success",
                "suspect_ids": ocr_res.get("suspect_ids", []),
                "map_name": ocr_res.get("map_name", ""),
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": media_type,
            }
        except Exception as err:
            LOGGER.error("process_imported_file error: %s", err)
            return {
                "status": "success",
                "suspect_ids": [],
                "map_name": self.config.get("default_map", ""),
                "ocr_map_name": "",
                "map_name_source": "default",
                "media_path": file_path,
                "media_type": "video",
            }

    def recognize_video_frame(
        self, file_path: str, timestamp_sec: float
    ) -> dict[str, Any]:
        """Recognize one paused video frame without replacing the evidence video."""
        if not file_path or not os.path.exists(file_path):
            return {"status": "error", "message": "檔案不存在"}

        if Path(file_path).suffix.lower() not in {".mp4", ".mkv", ".avi", ".mov"}:
            return {"status": "error", "message": "目前證據不是影片"}

        try:
            timestamp = max(0.0, float(timestamp_sec))
            frame = self.capture_controller.capture_video_frame(file_path, timestamp)
            if frame is None:
                return {"status": "error", "message": "無法擷取目前影片畫面"}

            ocr_res = self._perform_ocr([frame])
            if ocr_res.get("cancelled"):
                return {"status": "cancelled", "message": "辨識已取消"}

            return {
                "status": "success",
                "suspect_ids": ocr_res.get("suspect_ids", []),
                "map_name": ocr_res.get("map_name", ""),
                "ocr_map_name": ocr_res.get("ocr_map_name", ""),
                "map_name_source": ocr_res.get("map_name_source", "default"),
                "media_path": file_path,
                "media_type": "video",
                "frame_time": timestamp,
            }
        except (OSError, TypeError, ValueError) as err:
            LOGGER.error("recognize_video_frame error: %s", err)
            return {"status": "error", "message": f"目前畫面辨識失敗: {err}"}
        except Exception as err:
            LOGGER.error("recognize_video_frame error: %s", err)
            return {"status": "error", "message": f"目前畫面辨識失敗: {err}"}

    def get_media_preview(self, file_path: str) -> str:
        """Return base64 data URL for an image or video thumbnail."""
        if not file_path or not os.path.exists(file_path):
            return ""
        try:
            ext = Path(file_path).suffix.lower()
            if ext in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
                with open(file_path, "rb") as f:
                    data = f.read()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                b64 = base64.b64encode(data).decode("utf-8")
                return f"data:{mime};base64,{b64}"
            elif ext in {".mp4", ".mkv", ".avi", ".mov"}:
                keyframes = self.capture_controller.load_keyframes(file_path)
                if keyframes and len(keyframes) > 0:
                    buffered = io.BytesIO()
                    keyframes[0].save(buffered, format="JPEG", quality=85)
                    b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
                    return f"data:image/jpeg;base64,{b64}"
        except Exception as err:
            LOGGER.warning("Failed to generate media preview for %s: %s", file_path, err)
        return ""

    def get_media_stream_url(self, file_path: str) -> str:
        """Return streaming HTTP URL for local media file to support HTML5 video playback."""
        if not file_path or not os.path.exists(file_path):
            return ""
        if not getattr(self, "media_server", None) or not self.media_server.port:
            if getattr(self, "media_server", None):
                self.media_server.start()
        port = getattr(self.media_server, "port", None) if getattr(self, "media_server", None) else None
        if not port:
            return ""
        encoded = base64.urlsafe_b64encode(file_path.encode("utf-8")).decode("utf-8")
        return f"http://127.0.0.1:{port}/media?path={encoded}"

    def trim_video_segment(
        self,
        file_path: str,
        cut_start: float,
        cut_end: float,
        original_backup_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Cut out a segment [cut_start, cut_end] from the video file.
        Preserves original backup and outputs standard cleanly named video.
        """
        if not file_path or not os.path.exists(file_path):
            return {"success": False, "error": "檔案不存在"}

        try:
            # 1. Determine backup path
            rec_dir = get_recordings_dir()
            backup_file = original_backup_path
            if not backup_file or not os.path.exists(backup_file):
                # Create original backup
                backup_name = f".backup_{Path(file_path).name}"
                backup_file = str(rec_dir / backup_name)
                shutil.copy2(file_path, backup_file)
                LOGGER.info("Created original backup at %s", backup_file)

            # 2. Prepare target output path with clean name
            timestamp = time.time_ns() // 1_000_000
            target_path = str(rec_dir / f"maple_evidence_replay_{timestamp}.mp4")

            # 3. Perform cut
            ok = cut_video_segment(file_path, cut_start, cut_end, target_path)
            if not ok or not os.path.exists(target_path):
                return {"success": False, "error": "影片區段剪輯失敗"}

            new_duration = get_video_duration(target_path)
            stream_url = self.get_media_stream_url(target_path)

            return {
                "success": True,
                "new_path": target_path,
                "duration": new_duration,
                "stream_url": stream_url,
                "original_backup_path": backup_file,
            }
        except Exception as err:
            LOGGER.error("trim_video_segment failed: %s", err, exc_info=True)
            return {"success": False, "error": str(err)}

    def restore_original_video(self, current_path: str, backup_path: str) -> dict[str, Any]:
        """Restore edited video back to original backup."""
        if not backup_path or not os.path.exists(backup_path):
            return {"success": False, "error": "找不到原始備份影片"}

        try:
            rec_dir = get_recordings_dir()
            timestamp = time.time_ns() // 1_000_000
            restored_path = str(rec_dir / f"maple_evidence_replay_{timestamp}.mp4")
            shutil.copy2(backup_path, restored_path)

            new_duration = get_video_duration(restored_path)
            stream_url = self.get_media_stream_url(restored_path)

            return {
                "success": True,
                "restored_path": restored_path,
                "duration": new_duration,
                "stream_url": stream_url,
            }
        except Exception as err:
            LOGGER.error("restore_original_video failed: %s", err)
            return {"success": False, "error": str(err)}

    def clear_all_recordings(self) -> dict[str, Any]:
        """Delete all media files in recordings directory and return count and freed bytes."""
        rec_dir = get_recordings_dir()
        files = [f for f in rec_dir.iterdir() if f.is_file()]
        deleted = 0
        total_bytes = 0
        for f in files:
            try:
                size = f.stat().st_size
                f.unlink()
                deleted += 1
                total_bytes += size
            except OSError as err:
                LOGGER.warning("Failed to delete %s: %s", f.name, err)

        if total_bytes < 1024:
            size_str = f"{total_bytes} B"
        elif total_bytes < 1024 * 1024:
            size_str = f"{total_bytes / 1024:.1f} KB"
        else:
            size_str = f"{total_bytes / (1024 * 1024):.1f} MB"

        return {
            "success": True,
            "count": deleted,
            "total_bytes": total_bytes,
            "size_str": size_str,
        }
