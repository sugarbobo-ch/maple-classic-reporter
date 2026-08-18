"""Lightweight background HTTP server for streaming local evidence media to PyWebView."""

from __future__ import annotations

import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
import mimetypes
import os
from pathlib import Path
import shutil
import threading
import urllib.parse

LOGGER = logging.getLogger(__name__)


class _RangeMediaRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler supporting Byte-Range requests for seamless HTML5 video seeking."""

    def log_message(self, format, *args):
        pass  # suppress standard access logging

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Accept")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/media":
            self.send_error(404, "Not Found")
            return

        query = urllib.parse.parse_qs(parsed.query)
        encoded_path = query.get("path", [""])[0]
        if not encoded_path:
            self.send_error(400, "Missing path")
            return

        try:
            file_path = base64.urlsafe_b64decode(encoded_path.encode("utf-8")).decode("utf-8")
        except Exception:
            self.send_error(400, "Invalid path encoding")
            return

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            self.send_error(404, "File Not Found")
            return

        file_size = os.path.getsize(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "video/mp4" if file_path.lower().endswith(".mp4") else "application/octet-stream"

        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            try:
                ranges = range_header[6:].split("-")
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if ranges[1] else file_size - 1
                if start >= file_size or end >= file_size or start > end:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    return
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(file_path, "rb") as f:
                    f.seek(start)
                    bytes_remaining = length
                    while bytes_remaining > 0:
                        chunk_size = min(65536, bytes_remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        bytes_remaining -= len(chunk)
            except (ConnectionResetError, BrokenPipeError):
                pass
            except Exception as e:
                LOGGER.debug("Streaming range error: %s", e)
        else:
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            try:
                with open(file_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile, length=65536)
            except (ConnectionResetError, BrokenPipeError):
                pass


class LocalMediaServer:
    """Lightweight background HTTP server for streaming local evidence media to WebView."""

    def __init__(self):
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    def start(self) -> int:
        if self._server:
            return self.port
        try:
            self._server = HTTPServer(("127.0.0.1", 0), _RangeMediaRequestHandler)
            self.port = self._server.server_port
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            LOGGER.info("LocalMediaServer started on port %d", self.port)
            return self.port
        except Exception as err:
            LOGGER.warning("Failed to start LocalMediaServer: %s", err)
            return 0

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
            self._thread = None
