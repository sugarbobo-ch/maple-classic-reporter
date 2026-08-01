import os
from typing import Tuple

import requests

_DEFAULT_DISCORD_FILE_LIMIT = 10 * 1024 * 1024


def upload_evidence_to_discord(webhook_url: str, file_path: str, description: str) -> Tuple[bool, str]:
    """Upload a local evidence file through an incoming Discord webhook."""
    if not webhook_url:
        return True, ""
    if not os.path.isfile(file_path):
        return False, "找不到要備份到 Discord 的事證檔案。"
    if os.path.getsize(file_path) > _DEFAULT_DISCORD_FILE_LIMIT:
        return False, "檔案過大，請使用 Google Drive 上傳。"
    try:
        with open(file_path, "rb") as evidence_file:
            response = requests.post(
                webhook_url,
                params={"wait": "true"},
                data={"content": description},
                files={"files[0]": (os.path.basename(file_path), evidence_file)},
                timeout=30,
            )
        if not response.ok:
            if response.status_code == 413:
                return False, "檔案過大，請使用 Google Drive 上傳。"
            return False, f"Discord 上傳失敗 ({response.status_code}): {response.text[:200]}"
        attachments = response.json().get("attachments", [])
        if not attachments or not attachments[0].get("url"):
            return False, "Discord 未回傳附件網址。"
        return True, attachments[0]["url"]
    except requests.RequestException as exc:
        return False, f"Discord 上傳失敗: {exc}"
