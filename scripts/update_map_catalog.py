"""Build the offline Artale map-name catalogue used by local OCR matching."""
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE_URL = "https://www.artalemaplestory.com/zh/maps"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "src" / "maple_reporter" / "ocr" / "data" / "map_names_zh.json"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._anchors: list[list] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._anchors.append([dict(attrs).get("href", ""), []])

    def handle_data(self, data):
        if self._anchors:
            self._anchors[-1][1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._anchors:
            href, parts = self._anchors.pop()
            self.links.append((href, "".join(parts).strip()))


def get_links(url: str) -> list[tuple[str, str]]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    parser = LinkParser()
    parser.feed(response.text)
    return parser.links


def main():
    index_links = get_links(BASE_URL)
    region_paths = sorted({href for href, _ in index_links if href.startswith("/zh/maps/") and href.count("/") == 3})
    map_names: list[str] = []
    seen: set[str] = set()
    for region_path in region_paths:
        for href, title in get_links(urljoin(BASE_URL, region_path)):
            if not href.startswith(region_path + "/") or not title or title in seen:
                continue
            seen.add(title)
            map_names.append(title)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({"source": BASE_URL, "maps": map_names}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(map_names)} map names to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
