"""CRUD and safe-open operations for user-configured quick links."""

from __future__ import annotations

import time
import webbrowser
from typing import Any

from maple_reporter.utils.config import save_config
from maple_reporter.utils.urls import is_safe_https_url


class QuickLinksController:
    """Keep quick-link behavior independent from the PySide widget layout."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def links(self) -> list[dict[str, Any]]:
        value = self.config.get("quick_links", [])
        if not isinstance(value, list):
            return []
        return [dict(item) for item in value if isinstance(item, dict)]

    @staticmethod
    def normalize_url(value: str) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if "://" not in text:
            text = f"https://{text}"
        return text if is_safe_https_url(text) else None

    def _persist(self, links: list[dict[str, Any]]) -> bool:
        previous = self.config.get("quick_links")
        self.config["quick_links"] = links
        try:
            save_config(self.config)
        except Exception:
            if previous is None:
                self.config.pop("quick_links", None)
            else:
                self.config["quick_links"] = previous
            return False
        return True

    def add(self, title: str, url: str, icon: str = "Globe") -> bool:
        clean_title = str(title or "").strip()
        clean_url = self.normalize_url(url)
        if not clean_title or not clean_url:
            return False

        links = self.links()
        links.append(
            {
                "id": str(time.time_ns()),
                "title": clean_title,
                "url": clean_url,
                "icon": str(icon or "Globe"),
                "isDefault": False,
            }
        )
        return self._persist(links)

    def update(self, index: int, title: str, url: str, icon: str | None = None) -> bool:
        clean_title = str(title or "").strip()
        clean_url = self.normalize_url(url)
        links = self.links()
        if not clean_title or not clean_url or not 0 <= index < len(links):
            return False

        item = links[index]
        item["title"] = clean_title
        item["url"] = clean_url
        if icon is not None:
            item["icon"] = str(icon or "Globe")
        return self._persist(links)

    def remove(self, index: int) -> bool:
        links = self.links()
        if not 0 <= index < len(links):
            return False
        del links[index]
        return self._persist(links)

    def move(self, index: int, delta: int) -> bool:
        links = self.links()
        target = index + delta
        if not 0 <= index < len(links) or not 0 <= target < len(links):
            return False
        links[index], links[target] = links[target], links[index]
        return self._persist(links)

    def open(self, index: int) -> bool:
        links = self.links()
        if not 0 <= index < len(links):
            return False
        return self.open_url(str(links[index].get("url", "")))

    @staticmethod
    def open_url(url: str) -> bool:
        if not is_safe_https_url(url):
            return False
        try:
            return bool(webbrowser.open(url))
        except OSError:
            return False


__all__ = ["QuickLinksController"]
