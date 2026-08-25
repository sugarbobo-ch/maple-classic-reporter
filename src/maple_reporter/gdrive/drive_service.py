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

import requests
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
GOOGLE_OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
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
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans TC", sans-serif;
      --color-primary: #a95517;
      --color-primary-subtle: #f8eee3;
      --color-bg: #faf8f5;
      --color-surface: #f4efea;
      --color-surface-card: #ffffff;
      --color-text: #292524;
      --color-heading: #633719;
      --color-secondary: #665e57;
      --color-muted: #70675f;
      --color-border: #d8cec1;
      --color-success: #4b7a24;
      --color-success-bg: #edf6e8;
      --color-danger: #a32820;
      --color-danger-bg: #fbeceb;
      background: var(--color-bg);
      color: var(--color-text);
    }
    * { box-sizing: border-box; }
    ::selection {
      background: var(--color-primary-subtle);
      color: var(--color-heading);
    }
    body {
      min-height: 100vh;
      min-height: 100dvh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: clamp(20px, 5vw, 56px);
      background: var(--color-bg);
      -webkit-font-smoothing: antialiased;
      text-rendering: optimizeLegibility;
    }
    main {
      width: min(100%, 560px);
      overflow: hidden;
      border: 1px solid var(--color-border);
      border-radius: 12px;
      background: var(--color-surface-card);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 60px;
      padding: 14px 20px;
      border-bottom: 1px solid var(--color-border);
      background: var(--color-surface);
      color: var(--color-heading);
      font-size: 0.875rem;
      font-weight: 700;
      letter-spacing: -0.01em;
    }
    .brand-mark {
      width: 28px;
      height: 28px;
      flex: 0 0 auto;
      color: var(--color-primary);
    }
    .brand span { text-wrap: balance; }
    .result {
      display: grid;
      grid-template-columns: 56px minmax(0, 1fr);
      gap: 18px;
      padding: clamp(28px, 7vw, 42px) clamp(22px, 7vw, 40px) 30px;
    }
    .result-icon {
      width: 56px;
      height: 56px;
      display: block;
    }
    .result-copy { min-width: 0; }
    h1 {
      max-width: 18ch;
      margin: 1px 0 10px;
      color: var(--color-heading);
      font-size: clamp(1.45rem, 5vw, 1.85rem);
      font-weight: 750;
      line-height: 1.25;
      letter-spacing: -0.025em;
      text-wrap: balance;
    }
    p {
      max-width: 42ch;
      margin: 0;
      color: var(--color-secondary);
      font-size: 0.95rem;
      line-height: 1.7;
    }
    .status {
      margin: 18px 0 0;
      font-size: 0.84rem;
      font-weight: 650;
      line-height: 1.5;
    }
    .success .status { color: var(--color-success); }
    .failure .status { color: var(--color-danger); }
    .note {
      max-width: none;
      padding: 15px clamp(22px, 7vw, 40px);
      border-top: 1px solid var(--color-border);
      background: var(--color-surface);
      color: var(--color-muted);
      font-size: 0.78rem;
      line-height: 1.55;
    }
    @media (max-width: 420px) {
      body { padding: 12px; }
      .brand { padding-inline: 16px; }
      .result {
        grid-template-columns: 44px minmax(0, 1fr);
        gap: 14px;
        padding: 24px 18px 26px;
      }
      .result-icon { width: 44px; height: 44px; }
      h1 { margin-top: 0; }
      .note { padding-inline: 18px; }
    }
    @media (max-width: 360px) {
      .result {
        grid-template-columns: minmax(0, 1fr);
        gap: 14px;
      }
      h1 { word-break: keep-all; }
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --color-primary: #d69a5e;
        --color-primary-subtle: rgb(214 154 94 / 20%);
        --color-bg: #1c1917;
        --color-surface: #26221f;
        --color-surface-card: #201c19;
        --color-text: #eae4dc;
        --color-heading: #e2cbb0;
        --color-secondary: #b1a59a;
        --color-muted: #9b9086;
        --color-border: #3d352e;
        --color-success: #86c85a;
        --color-success-bg: rgb(75 122 36 / 24%);
        --color-danger: #f08078;
        --color-danger-bg: rgb(163 40 32 / 24%);
      }
    }
    @media (forced-colors: active) {
      main, .brand, .note { border-color: CanvasText; }
    }
  </style>
</head>
<body>
  <main class="__RESULT_CLASS__" aria-labelledby="page-title">
    <header class="brand">
      <svg class="brand-mark" viewBox="0 0 28 28" aria-hidden="true">
        <rect x="2" y="6" width="24" height="17" rx="4" fill="currentColor" opacity=".16"/>
        <path d="M7 10.5h3l1.5-2h5l1.5 2h3v8H7z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>
        <circle cx="14" cy="14.5" r="2.7" fill="none" stroke="currentColor" stroke-width="1.8"/>
      </svg>
      <span>新楓之谷：經典版《自動外掛檢舉工具》</span>
    </header>
    <section class="result">
      __RESULT_ICON__
      <div class="result-copy">
        <h1 id="page-title">__HEADING__</h1>
        <p>__DESCRIPTION__</p>
        <p class="status" role="status" aria-live="polite">__STATUS__</p>
      </div>
    </section>
    <p class="note">__NOTE__</p>
  </main>
</body>
</html>
"""

SUCCESS_ICON = """<svg class="result-icon" viewBox="0 0 56 56" aria-hidden="true">
  <rect x="1" y="1" width="54" height="54" rx="12" fill="var(--color-success-bg)"/>
  <path d="M17 28.5 24.5 36 39.5 20.5" fill="none" stroke="var(--color-success)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

FAILURE_ICON = """<svg class="result-icon" viewBox="0 0 56 56" aria-hidden="true">
  <rect x="1" y="1" width="54" height="54" rx="12" fill="var(--color-danger-bg)"/>
  <path d="m19 19 18 18M37 19 19 37" fill="none" stroke="var(--color-danger)" stroke-width="4" stroke-linecap="round"/>
</svg>"""


def make_oauth_result_html(*, success: bool) -> str:
    """Build a localized OAuth result page without exposing error details."""

    values = (
        {
            "__PAGE_TITLE__": "Google 帳號登入完成",
            "__RESULT_CLASS__": "success",
            "__RESULT_ICON__": SUCCESS_ICON,
            "__HEADING__": "Google 帳號登入完成",
            "__DESCRIPTION__": "授權已完成。現在可以關閉這個頁面，返回「新楓之谷自動外掛檢舉工具」繼續操作。",
            "__STATUS__": "Google 帳號已登入",
            "__NOTE__": "此頁面由本機程式（localhost）提供，不會顯示你的授權資料。",
        }
        if success
        else {
            "__PAGE_TITLE__": "Google 帳號登入失敗",
            "__RESULT_CLASS__": "failure",
            "__RESULT_ICON__": FAILURE_ICON,
            "__HEADING__": "Google 帳號登入失敗",
            "__DESCRIPTION__": "帳戶尚未連結，可能是授權被取消、連線中斷，或 Google 無法完成驗證。",
            "__STATUS__": "尚未登入 Google 帳號",
            "__NOTE__": "請關閉此頁面，返回應用程式後重新登入。",
        }
    )
    html = OAUTH_RESULT_HTML
    for placeholder, value in values.items():
        html = html.replace(placeholder, value)
    return html


OAUTH_SUCCESS_HTML = make_oauth_result_html(success=True)
OAUTH_FAILURE_HTML = make_oauth_result_html(success=False)
OAUTH_LOGIN_TIMEOUT_SECONDS = 5 * 60


class OAuthLoginTimeoutError(RuntimeError):
    """Raised when the browser does not complete OAuth within the wait limit."""


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
    local_server.timeout = OAUTH_LOGIN_TIMEOUT_SECONDS
    try:
        flow.redirect_uri = f"http://{host}:{local_server.server_port}/"
        authorization_url, _ = flow.authorization_url()
        webbrowser.open(authorization_url, new=1, autoraise=True)
        local_server.handle_request()
        if callback_page.last_request_uri is None:
            raise OAuthLoginTimeoutError("5 分鐘內未完成 Google 帳號登入。")
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
            return True, "Google 帳號已登入，之後可直接使用 Google Drive。"
        except OAuthLoginTimeoutError:
            return False, "Google 帳號登入已逾時（5 分鐘未完成），請重新登入。"
        except OAuthConfigError as error:
            return False, str(error)
        except Exception as error:
            LOGGER.warning("Google OAuth 登入失敗 (%s)", type(error).__name__)
            return False, "Google 帳號登入失敗，請稍後重新登入。"

    def disconnect(self, *, revoke: bool = True) -> dict[str, object]:
        """Revoke Google access when possible and always clear local credentials."""

        token = None
        if self.creds is not None:
            token = self.creds.refresh_token or self.creds.token

        remote_revoked: bool | None = None
        requires_manual_revoke = False
        if revoke and token:
            try:
                response = requests.post(
                    GOOGLE_OAUTH_REVOKE_URL,
                    data={"token": token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10,
                )
                remote_revoked = response.status_code == 200
                requires_manual_revoke = not remote_revoked
                if not remote_revoked:
                    LOGGER.warning(
                        "Google OAuth revoke failed (status=%s)",
                        response.status_code,
                    )
            except Exception as error:
                remote_revoked = False
                requires_manual_revoke = True
                LOGGER.warning(
                    "Google OAuth revoke request failed (%s)",
                    type(error).__name__,
                )

        local_error: Exception | None = None
        try:
            self.token_store.delete()
            self._delete_legacy_token()
        except OSError as error:
            local_error = error
            LOGGER.warning(
                "Google OAuth local credential cleanup failed (%s)",
                type(error).__name__,
            )
        finally:
            self.creds = None
            self.service = None
            self._loaded_from_legacy_token = False

        if local_error is not None:
            return {
                "success": False,
                "is_authenticated": False,
                "remote_revoked": remote_revoked,
                "requires_manual_revoke": requires_manual_revoke,
                "message": "無法完整移除這台電腦的 Google 登入資料，請關閉程式後再試。",
            }
        if requires_manual_revoke:
            return {
                "success": True,
                "is_authenticated": False,
                "remote_revoked": False,
                "requires_manual_revoke": True,
                "message": "這台電腦已登出，但無法連線撤銷 Google 授權。",
            }
        return {
            "success": True,
            "is_authenticated": False,
            "remote_revoked": remote_revoked,
            "requires_manual_revoke": False,
            "message": "Google 帳號已登出。",
        }

    def get_or_create_folder(self, folder_name: str = "MapleClassic_Reports") -> str:
        """Get or create the dedicated report folder in Google Drive."""

        if not self.service:
            raise RuntimeError("Google 帳號尚未登入。")

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
            return False, "Google 帳號尚未完成登入驗證，請先登入 Google 帳號。"

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

    def trash_file(self, file_id: str) -> tuple[bool, str]:
        """Move an app-managed Drive file to the user's Drive trash."""

        normalized_id = str(file_id or "").strip()
        if not normalized_id:
            return False, "找不到 Google Drive file ID。"
        if not self.is_authenticated() or self.service is None:
            return False, "Google 帳號尚未完成登入驗證，請先登入 Google 帳號。"
        try:
            existing = self.service.files().get(
                fileId=normalized_id,
                fields="id,trashed",
            ).execute()
            if existing.get("trashed"):
                return True, "Google Drive 檔案已在垃圾桶。"
            self.service.files().update(
                fileId=normalized_id,
                body={"trashed": True},
                fields="id,trashed",
            ).execute()
            return True, "Google Drive 檔案已移至垃圾桶。"
        except Exception as error:
            LOGGER.warning("Google Drive 清理失敗 (%s)", type(error).__name__)
            return False, "無法將 Google Drive 檔案移至垃圾桶，請確認帳號權限後重試。"
