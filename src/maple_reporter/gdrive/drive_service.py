import os
import json
import mimetypes
from pathlib import Path
from typing import Optional, Tuple
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from maple_reporter.utils.config import CONFIG_DIR

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

class GoogleDriveManager:
    def __init__(self, token_path: str = "token.json"):
        self.token_path = token_path
        self.creds: Optional[Credentials] = None
        self.service = None
        self._load_credentials()

    def _load_credentials(self) -> bool:
        if os.path.exists(self.token_path):
            try:
                self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception:
                self.creds = None

        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                with open(self.token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(self.creds.to_json())
            except Exception:
                self.creds = None

        if self.creds and self.creds.valid:
            try:
                self.service = build("drive", "v3", credentials=self.creds)
                return True
            except Exception:
                self.service = None
        return False

    def is_authenticated(self) -> bool:
        return self.creds is not None and self.creds.valid and self.service is not None

    def authenticate_interactive(self, client_secrets_dict_or_path=None) -> Tuple[bool, str]:
        """
        Run Google OAuth2 PKCE login flow.
        """
        try:
            if isinstance(client_secrets_dict_or_path, dict):
                flow = InstalledAppFlow.from_client_config(client_secrets_dict_or_path, SCOPES)
            elif client_secrets_dict_or_path and os.path.exists(client_secrets_dict_or_path):
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_dict_or_path, SCOPES)
            else:
                secret_paths = [
                    CONFIG_DIR / "client_secrets.json",
                    Path("client_secrets.json"),  # Legacy project-root location.
                    Path.home() / ".maple_reporter" / "client_secrets.json",  # Legacy location.
                ]
                secret_path = next((path for path in secret_paths if path.exists()), None)
                if secret_path:
                    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)
                else:
                    return False, (
                        "未找到有效的 Google OAuth 用戶端憑證檔案 (client_secrets.json)。\n\n"
                        "【解決步驟】:\n"
                        "1. 請前往 Google Cloud Console (https://console.cloud.google.com/)\n"
                        "2. 建立專案並啟用 'Google Drive API'\n"
                        "3. 建立憑證 -> 'OAuth 2.0 用戶端 ID' (類型選擇 '桌面應用程式 Desktop App')\n"
                        "4. 下載憑證 JSON 檔案，將其重新命名為 'client_secrets.json'\n"
                        "5. 放置於 data\\config\\client_secrets.json"
                    )

            self.creds = flow.run_local_server(port=0)
            token_dir = os.path.dirname(self.token_path)
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)
            with open(self.token_path, "w", encoding="utf-8") as token_file:
                token_file.write(self.creds.to_json())

            self.service = build("drive", "v3", credentials=self.creds)
            return True, "登入成功！"
        except Exception as e:
            return False, f"OAuth 登入失敗: {str(e)}"

    def get_or_create_folder(self, folder_name: str = "MapleClassic_Reports") -> str:
        """Get or create dedicated report folder in Google Drive."""
        if not self.service:
            raise RuntimeError("Google Drive 未登入服務")

        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])

        if files:
            return files[0]["id"]

        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = self.service.files().create(body=folder_metadata, fields="id").execute()
        return folder.get("id")

    def get_folder_url(self, folder_name: str = "MapleClassic_Reports") -> Optional[str]:
        """Return the web URL to open the target report folder in Google Drive."""
        if not self.is_authenticated():
            return None
        try:
            folder_id = self.get_or_create_folder(folder_name)
            return f"https://drive.google.com/drive/folders/{folder_id}"
        except Exception:
            return None

    def upload_file_and_make_public(self, file_path: str, folder_name: str = "MapleClassic_Reports") -> Tuple[bool, str]:
        """
        Upload file to Google Drive, set permission to 'anyone:reader',
        and return the webViewLink URL.
        """
        if not self.is_authenticated():
            return False, "Google Drive 尚未完成登入驗證，請先於主視窗設定中登入！"

        try:
            folder_id = self.get_or_create_folder(folder_name)
            file_name = os.path.basename(file_path)

            ext = os.path.splitext(file_name)[1].lower()
            mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

            file_metadata = {
                "name": file_name,
                "parents": [folder_id]
            }
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)

            uploaded_file = self.service.files().create(
                body=file_metadata, media_body=media, fields="id, webViewLink"
            ).execute()

            file_id = uploaded_file.get("id")
            web_link = uploaded_file.get("webViewLink")

            # Set file permission to anyone reader (公開分享)
            permission_body = {
                "type": "anyone",
                "role": "reader"
            }
            self.service.permissions().create(
                fileId=file_id,
                body=permission_body,
                fields="id"
            ).execute()

            return True, web_link or f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        except Exception as e:
            return False, f"上傳檔案失敗: {str(e)}"
