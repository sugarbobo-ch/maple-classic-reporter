"""Google Drive OAuth and evidence-upload helpers.

The OAuth *client* configuration is an application resource. Release builds
carry it inside the PyInstaller bundle, while refresh tokens are protected
with Windows DPAPI in the user's local application-data directory.
"""

from __future__ import annotations

import mimetypes
import json
import logging
import os
import sys
import webbrowser
import wsgiref.simple_server
import wsgiref.util
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from maple_reporter.gdrive.token_store import (
    ProtectedTokenStore,
    ProtectedTokenStoreError,
)
from maple_reporter.utils.config import (
    CONFIG_DIR,
    LEGACY_CONFIG_DIR,
    get_default_token_path,
)


LOGGER = logging.getLogger(__name__)


SCOPES = ["https://www.googleapis.com/auth/drive.file"]
GOOGLE_OAUTH_CONFIG_ENV_VAR = "MAPLE_REPORTER_GOOGLE_OAUTH_CONFIG"
BUNDLED_OAUTH_CONFIG_FILENAME = "google_oauth_client.json"
RELEASE_OAUTH_CONFIG_RELATIVE_PATH = Path("build_secrets") / BUNDLED_OAUTH_CONFIG_FILENAME
LEGACY_OAUTH_CONFIG_FILENAME = "client_secrets.json"
PROJECT_ROOT = Path(__file__).resolve().parents[3]

OAUTH_RESULT_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>__PAGE_TITLE__</title>
  <style>
    :root {
      color-scheme: light dark;
      font-family: system-ui, -apple-system, "Segoe UI", "Noto Sans TC", sans-serif;
      background: #f3f6fb;
      color: #172033;
    }
    * { box-sizing: border-box; }
    body {
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      background: radial-gradient(circle at top, #e8f1ff 0, #f3f6fb 48%);
    }
    main {
      width: min(100%, 500px);
      padding: 40px;
      border-radius: 20px;
      background: #ffffff;
      box-shadow: 0 0 0 1px rgb(23 32 51 / 8%), 0 18px 48px rgb(23 32 51 / 12%);
      text-align: center;
    }
    .result-icon {
      width: 72px;
      height: 72px;
      margin: 0 auto 24px;
      display: block;
    }
    h1 { margin: 0 0 12px; font-size: clamp(1.6rem, 6vw, 2rem); line-height: 1.25; }
    p { margin: 0; color: #526078; line-height: 1.7; }
    .status {
      margin: 24px 0 16px;
      padding: 12px 16px;
      border-radius: 12px;
      font-weight: 700;
    }
    .success .status { background: #e7f6ec; color: #0d652d; }
    .failure .status { background: #fde8e7; color: #a3261d; }
    .note { font-size: 0.875rem; }
    @media (prefers-color-scheme: dark) {
      :root { background: #10131a; color: #f4f7ff; }
      body { background: radial-gradient(circle at top, #17243a 0, #10131a 48%); }
      main {
        background: #191e29;
        box-shadow: 0 0 0 1px rgb(255 255 255 / 10%), 0 18px 48px rgb(0 0 0 / 28%);
      }
      p { color: #b8c1d5; }
      .success .status { background: #153d24; color: #8ce5a8; }
      .failure .status { background: #49201f; color: #ffaaa3; }
    }
  </style>
</head>
<body>
  <main class="__RESULT_CLASS__" aria-labelledby="page-title">
    __RESULT_ICON__
    <h1 id="page-title">__HEADING__</h1>
    <p>__DESCRIPTION__</p>
    <div class="status" role="status">__STATUS__</div>
    <p class="note">__NOTE__</p>
  </main>
</body>
</html>
"""

SUCCESS_ICON = """<svg class="result-icon" viewBox="0 0 72 72" aria-hidden="true">
  <circle cx="36" cy="36" r="34" fill="#1f8f4e"/>
  <path d="M21 37.5 31.5 48 52 26" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

FAILURE_ICON = """<svg class="result-icon" viewBox="0 0 72 72" aria-hidden="true">
  <circle cx="36" cy="36" r="34" fill="#c43c35"/>
  <path d="m25 25 22 22M47 25 25 47" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>
</svg>"""


def make_oauth_result_html(*, success: bool) -> str:
    """Build a localized OAuth result page without exposing error details."""

    values = (
        {
            "__PAGE_TITLE__": "Google 帳號連結完成",
            "__RESULT_CLASS__": "success",
            "__RESULT_ICON__": SUCCESS_ICON,
            "__HEADING__": "Google 帳號連結完成",
            "__DESCRIPTION__": "授權已完成。現在可以關閉這個頁面，返回「新楓之谷自動外掛檢舉工具」繼續操作。",
            "__STATUS__": "Google Drive 已連結",
            "__NOTE__": "此頁面由本機程式（localhost）提供，不會顯示你的授權資料。",
        }
        if success
        else {
            "__PAGE_TITLE__": "Google 帳號連結失敗",
            "__RESULT_CLASS__": "failure",
            "__RESULT_ICON__": FAILURE_ICON,
            "__HEADING__": "Google 帳號連結失敗",
            "__DESCRIPTION__": "帳戶尚未連結，可能是授權被取消、連線中斷，或 Google 無法完成驗證。",
            "__STATUS__": "未連結 Google Drive",
            "__NOTE__": "請關閉此頁面，返回應用程式後重新授權。",
        }
    )
    html = OAUTH_RESULT_HTML
    for placeholder, value in values.items():
        html = html.replace(placeholder, value)
    return html


OAUTH_SUCCESS_HTML = make_oauth_result_html(success=True)
OAUTH_FAILURE_HTML = make_oauth_result_html(success=False)


class OAuthSuccessPage:
    """Exchange the callback token and render the matching localized result."""

    def __init__(self, flow: InstalledAppFlow | None = None):
        self.flow = flow
        self.last_request_uri: Optional[str] = None
        self.error: Exception | None = None

    def __call__(
        self,
        environ: Mapping[str, object],
        start_response: Callable[[str, list[tuple[str, str]]], object],
    ) -> Iterable[bytes]:
        self.last_request_uri = wsgiref.util.request_uri(environ)
        status = "200 OK"
        html = OAUTH_SUCCESS_HTML
        if self.flow is not None:
            authorization_response = self.last_request_uri
            if authorization_response.startswith("http://"):
                authorization_response = "https://" + authorization_response[7:]
            try:
                self.flow.fetch_token(authorization_response=authorization_response)
            except Exception as error:
                self.error = error
                status = "400 Bad Request"
                html = OAUTH_FAILURE_HTML
        body = html.encode("utf-8")
        start_response(
            status,
            [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ],
        )
        return [body]


class OAuthCallbackServer(wsgiref.simple_server.WSGIServer):
    allow_reuse_address = False


def run_local_oauth_server(
    flow: InstalledAppFlow,
    host: str = "localhost",
    port: int = 0,
):
    """Complete InstalledAppFlow with a styled Traditional Chinese page."""

    callback_page = OAuthSuccessPage(flow)
    local_server = wsgiref.simple_server.make_server(
        host,
        port,
        callback_page,
        server_class=OAuthCallbackServer,
    )
    try:
        flow.redirect_uri = f"http://{host}:{local_server.server_port}/"
        authorization_url, _ = flow.authorization_url()
        webbrowser.open(authorization_url, new=1, autoraise=True)
        local_server.handle_request()
        if callback_page.last_request_uri is None:
            raise RuntimeError("等待 Google 授權回應時發生逾時。")
        if callback_page.error is not None:
            raise callback_page.error
        return flow.credentials
    finally:
        local_server.server_close()


class OAuthConfigError(FileNotFoundError):
    """Raised when a usable OAuth Desktop client configuration is unavailable."""


def escape_drive_query_literal(value: str) -> str:
    """Validate and escape a string used as a Google Drive query literal."""

    if not isinstance(value, str):
        raise TypeError("Google Drive folder name must be a string.")
    value = value.strip()
    if not value or len(value) > 100 or any(ord(char) < 32 for char in value):
        raise ValueError("Google Drive folder name is invalid.")
    return value.replace("\\", "\\\\").replace("'", "\\'")


def is_frozen() -> bool:
    """Return whether the application is running from a PyInstaller bundle."""

    return bool(getattr(sys, "frozen", False))


def get_frozen_resource_root() -> Optional[Path]:
    """Return PyInstaller's extracted resource directory for frozen builds."""

    if not is_frozen():
        return None
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))


def get_oauth_client_config_candidates() -> tuple[Path, ...]:
    """Return source-mode OAuth config candidates in precedence order.

    A frozen application intentionally uses only its embedded resource.  In
    source mode, an explicit environment override wins, followed by the
    ignored release-build secret and the legacy developer fallback.
    """

    frozen_root = get_frozen_resource_root()
    if frozen_root is not None:
        return (frozen_root / BUNDLED_OAUTH_CONFIG_FILENAME,)

    candidates: list[Path] = []
    environment_path = os.environ.get(GOOGLE_OAUTH_CONFIG_ENV_VAR, "").strip()
    if environment_path:
        candidates.append(Path(environment_path).expanduser())

    candidates.extend(
        (
            PROJECT_ROOT / RELEASE_OAUTH_CONFIG_RELATIVE_PATH,
            CONFIG_DIR / LEGACY_OAUTH_CONFIG_FILENAME,
            LEGACY_CONFIG_DIR / LEGACY_OAUTH_CONFIG_FILENAME,
            PROJECT_ROOT / LEGACY_OAUTH_CONFIG_FILENAME,
            Path.home() / ".maple_reporter" / LEGACY_OAUTH_CONFIG_FILENAME,
        )
    )

    # Keep the diagnostic/test surface deterministic when a path is repeated.
    return tuple(dict.fromkeys(candidates))


def resolve_oauth_client_config_path(
    client_secrets_path: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve the OAuth Desktop client JSON without copying it to user data.

    ``client_secrets_path`` is retained as an explicit developer/test escape
    hatch.  Normal source runs use ``MAPLE_REPORTER_GOOGLE_OAUTH_CONFIG`` or
    the ignored ``build_secrets`` path; frozen releases use the embedded file.
    """

    if client_secrets_path:
        explicit_path = Path(client_secrets_path).expanduser()
        if explicit_path.is_file():
            return explicit_path
        raise OAuthConfigError(
            f"指定的 Google OAuth 設定檔不存在：{explicit_path}"
        )

    candidates = get_oauth_client_config_candidates()
    environment_path = os.environ.get(GOOGLE_OAUTH_CONFIG_ENV_VAR, "").strip()
    if environment_path and not is_frozen():
        override_path = candidates[0]
        if not override_path.is_file():
            raise OAuthConfigError(
                "環境變數 "
                f"{GOOGLE_OAUTH_CONFIG_ENV_VAR} 指定的 Google OAuth 設定檔不存在："
                f"{override_path}"
            )
        return override_path

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    if is_frozen():
        raise OAuthConfigError(
            "此發行版缺少 Google 登入設定，請重新下載正式版本。"
        )

    raise OAuthConfigError(
        "找不到 Google OAuth Desktop client 設定。一般使用者不需要建立 "
        "client_secrets.json；開發者請設定 "
        f"{GOOGLE_OAUTH_CONFIG_ENV_VAR}，或準備 "
        "build_secrets/google_oauth_client.json。"
    )


class GoogleDriveManager:
    def __init__(self, token_path: str | os.PathLike[str] | None = None):
        self.token_path = (
            Path(token_path).expanduser()
            if token_path
            else get_default_token_path()
        )
        self.token_store = ProtectedTokenStore(self.token_path)
        self.legacy_token_paths = tuple(
            dict.fromkeys(
                (
                    CONFIG_DIR / "token.json",
                    LEGACY_CONFIG_DIR / "token.json",
                )
            )
        )
        self._loaded_from_legacy_token = False
        self.creds: Optional[Credentials] = None
        self.service = None
        self._load_credentials()

    def _save_credentials(self) -> None:
        """Persist the user's OAuth token in protected local storage."""

        if self.creds is None:
            raise ProtectedTokenStoreError("Cannot save missing OAuth credentials.")
        self.token_store.save(self.creds.to_json())

    def _delete_legacy_token(self) -> None:
        for legacy_token_path in self.legacy_token_paths:
            if legacy_token_path == self.token_path:
                continue
            try:
                legacy_token_path.unlink()
            except FileNotFoundError:
                pass

    def _load_token_info(self) -> dict | None:
        """Load protected credentials, or identify a legacy token to migrate."""

        if self.token_path not in self.legacy_token_paths:
            try:
                token_info = self.token_store.load()
            except ProtectedTokenStoreError as error:
                LOGGER.warning("讀取受保護 OAuth token 失敗 (%s)", type(error).__name__)
                token_info = None
            if token_info is not None:
                return token_info

        for legacy_token_path in self.legacy_token_paths:
            if not legacy_token_path.is_file():
                continue
            try:
                token_info = json.loads(
                    legacy_token_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
                LOGGER.warning(
                    "讀取舊版 OAuth token 失敗 (%s)", type(error).__name__
                )
                continue

            if isinstance(token_info, dict):
                self._loaded_from_legacy_token = True
                return token_info
        return None

    def _load_credentials(self) -> bool:
        token_info = self._load_token_info()
        if token_info is not None:
            try:
                self.creds = Credentials.from_authorized_user_info(token_info, SCOPES)
            except Exception as error:
                LOGGER.warning(
                    "OAuth token 格式無法解析 (%s)", type(error).__name__
                )
                self.creds = None

        credentials_persisted = False
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                credentials_persisted = True
            except Exception as error:
                LOGGER.warning("OAuth token 更新失敗 (%s)", type(error).__name__)
            else:
                try:
                    self._save_credentials()
                except Exception as error:
                    LOGGER.warning(
                        "OAuth token 更新後保存失敗 (%s)", type(error).__name__
                    )
                    credentials_persisted = False

        if self.creds and self.creds.valid:
            if self._loaded_from_legacy_token:
                try:
                    if not credentials_persisted:
                        self._save_credentials()
                    self._delete_legacy_token()
                except Exception as error:
                    LOGGER.warning(
                        "遷移 OAuth token 失敗 (%s)", type(error).__name__
                    )
                    self.creds = None
                    return False
            try:
                self.service = build("drive", "v3", credentials=self.creds)
                return True
            except Exception as error:
                LOGGER.warning("建立 Google Drive service 失敗 (%s)", type(error).__name__)
                self.service = None
        return False

    def is_authenticated(self) -> bool:
        if self.creds is None:
            return False

        if self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
            except Exception as error:
                LOGGER.warning(
                    "OAuth token 自動更新失敗 (%s)", type(error).__name__
                )
                return False
            try:
                self._save_credentials()
            except Exception as error:
                LOGGER.warning(
                    "OAuth token 更新後保存失敗 (%s)", type(error).__name__
                )

        if not self.creds.valid:
            return False

        if self.service is None:
            try:
                self.service = build("drive", "v3", credentials=self.creds)
            except Exception as error:
                LOGGER.warning(
                    "建立 Google Drive service 失敗 (%s)", type(error).__name__
                )
                self.service = None
        return self.service is not None

    def authenticate_interactive(
        self,
        client_secrets_dict_or_path: Mapping[str, object]
        | str
        | os.PathLike[str]
        | None = None,
    ) -> Tuple[bool, str]:
        """Run the InstalledAppFlow loopback OAuth login with a dynamic port."""

        try:
            if isinstance(client_secrets_dict_or_path, Mapping):
                flow = InstalledAppFlow.from_client_config(
                    dict(client_secrets_dict_or_path), SCOPES
                )
            else:
                client_config_path = resolve_oauth_client_config_path(
                    client_secrets_dict_or_path
                )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_config_path), SCOPES
                )

            self.creds = run_local_oauth_server(flow, host="localhost", port=0)
            self._save_credentials()
            self._delete_legacy_token()
            self.service = build("drive", "v3", credentials=self.creds)
            return True, "Google 帳號已連結，之後可直接使用 Google Drive。"
        except OAuthConfigError as error:
            return False, str(error)
        except Exception as error:
            LOGGER.warning("Google OAuth 登入失敗 (%s)", type(error).__name__)
            return False, "Google OAuth 登入失敗，請稍後重新授權。"

    def get_or_create_folder(self, folder_name: str = "MapleClassic_Reports") -> str:
        """Get or create the dedicated report folder in Google Drive."""

        if not self.service:
            raise RuntimeError("Google Drive 尚未登入服務。")

        escaped_folder_name = escape_drive_query_literal(folder_name)
        query = (
            "mimeType='application/vnd.google-apps.folder' "
            f"and name='{escaped_folder_name}' and trashed=false"
        )
        results = self.service.files().list(
            q=query, fields="files(id, name)"
        ).execute()
        files = results.get("files", [])

        if files:
            return files[0]["id"]

        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = self.service.files().create(
            body=folder_metadata, fields="id"
        ).execute()
        return folder.get("id")

    def get_folder_url(self, folder_name: str = "MapleClassic_Reports") -> Optional[str]:
        """Return the web URL to open the target report folder."""

        if not self.is_authenticated():
            return None
        try:
            folder_id = self.get_or_create_folder(folder_name)
            return f"https://drive.google.com/drive/folders/{folder_id}"
        except Exception as error:
            LOGGER.warning("讀取 Google Drive 資料夾失敗 (%s)", type(error).__name__)
            return None

    def upload_file_and_make_public(
        self,
        file_path: str,
        folder_name: str = "MapleClassic_Reports",
    ) -> Tuple[bool, str]:
        """Upload an evidence file and return its shareable Drive URL."""

        if not self.is_authenticated():
            return False, "Google Drive 尚未完成登入驗證，請先按「連結 Google 帳號」。"

        try:
            folder_id = self.get_or_create_folder(folder_name)
            file_name = os.path.basename(file_path)
            mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

            file_metadata = {"name": file_name, "parents": [folder_id]}
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

            uploaded_file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, webViewLink",
            ).execute()

            file_id = uploaded_file.get("id")
            web_link = uploaded_file.get("webViewLink")

            self.service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
            ).execute()

            return True, web_link or f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        except Exception as error:
            LOGGER.warning("Google Drive 上傳失敗 (%s)", type(error).__name__)
            return False, "上傳檔案失敗，請檢查 Google Drive 權限與網路後再試。"
