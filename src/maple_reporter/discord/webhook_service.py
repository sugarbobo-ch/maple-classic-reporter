import os
import re
from typing import Tuple
from urllib.parse import urlsplit

import requests

from maple_reporter.utils.urls import is_safe_https_url

_DEFAULT_DISCORD_FILE_LIMIT = 10 * 1024 * 1024
_DISCORD_WEBHOOK_PATH = re.compile(r"^/api/webhooks/[0-9]+/[A-Za-z0-9._-]+/?$")


def is_valid_discord_webhook_url(webhook_url: str) -> bool:
    """Allow only Discord HTTPS webhook endpoints, without redirects/aliases."""

    if not isinstance(webhook_url, str):
        return False
    try:
        parsed = urlsplit(webhook_url.strip())
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme.lower() == "https"
        and hostname in {"discord.com", "discordapp.com"}
        and port is None
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and bool(_DISCORD_WEBHOOK_PATH.fullmatch(parsed.path))
    )


def upload_evidence_to_discord(webhook_url: str, file_path: str, description: str) -> Tuple[bool, str]:
    """Upload a local evidence file through an incoming Discord webhook."""
    if not webhook_url:
        return True, ""
    if not is_valid_discord_webhook_url(webhook_url):
        return False, "Discord Webhook URL 必須是有效的 Discord HTTPS webhook。"
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
                allow_redirects=False,
            )
        if not 200 <= response.status_code < 300:
            if response.status_code == 413:
                return False, "檔案過大，請使用 Google Drive 上傳。"
            return False, f"Discord 上傳失敗 ({response.status_code}): {response.text[:200]}"
        try:
            attachments = response.json().get("attachments", [])
        except (TypeError, ValueError):
            return False, "Discord 回應不是有效的 JSON。"
        attachment_url = attachments[0].get("url") if attachments else ""
        if not attachment_url or not is_safe_https_url(attachment_url):
            return False, "Discord 未回傳附件網址。"
        return True, attachment_url
    except requests.RequestException as exc:
        return False, f"Discord 上傳失敗: {exc}"
