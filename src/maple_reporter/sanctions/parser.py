"""Parsers for official bulletin list JSON and announcement HTML tables."""

from __future__ import annotations

import html
import json
import logging
import re
from html.parser import HTMLParser
from typing import Any

from maple_reporter.sanctions.models import BulletinHeader, SanctionEntry

LOGGER = logging.getLogger(__name__)

OFFICIAL_ORIGIN = "https://maplestoryclassic.beanfun.com"
SANCTION_TITLE_KEYWORD = "遊戲異常行為制裁公告"


def normalize_date_str(raw_date: str) -> str:
    """Normalize date string (e.g., '2026/08/15 12:00:00' or '2026-08-15') to YYYY-MM-DD."""
    raw = raw_date.strip().replace("/", "-")
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw)
    if match:
        return match.group(1)
    return ""


def parse_bulletin_list_json(raw_bytes: bytes) -> list[BulletinHeader]:
    """Parse JSON response from FindBulletin API with UTF-8-SIG decoding.
    
    Filters specifically for announcements matching the sanction title keyword.
    """
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("utf-8", errors="replace")

    data = json.loads(text)
    items = []
    
    # Official API FindBulletin returns list in various candidate envelope paths
    # e.g., data.myDataSet.table or data.data or data directly
    candidate_lists = []
    
    def _extract_from_dict(d: dict) -> None:
        if isinstance(d.get("data"), list):
            candidate_lists.append(d["data"])
        elif isinstance(d.get("data"), dict):
            _extract_from_dict(d["data"])

        if isinstance(d.get("Data"), list):
            candidate_lists.append(d["Data"])
        elif isinstance(d.get("Data"), dict):
            _extract_from_dict(d["Data"])

        my_data_set = d.get("myDataSet") or d.get("MyDataSet")
        if isinstance(my_data_set, dict):
            table = my_data_set.get("table") or my_data_set.get("Table")
            if isinstance(table, list):
                candidate_lists.append(table)
            elif isinstance(table, dict):
                candidate_lists.append([table])

    if isinstance(data, list):
        candidate_lists.append(data)
    elif isinstance(data, dict):
        _extract_from_dict(data)

    headers: list[BulletinHeader] = []
    seen_bids: set[int] = set()

    for item_list in candidate_lists:
        for item in item_list:
            if not isinstance(item, dict):
                continue

            raw_bid = (
                item.get("bullentinId")
                or item.get("bulletinId")
                or item.get("bullentinID")
                or item.get("Bid")
                or item.get("bid")
                or item.get("pbid")
                or item.get("Id")
                or item.get("id")
            )
            if raw_bid is None:
                continue
            try:
                bid = int(raw_bid)
            except (ValueError, TypeError):
                continue

            if bid in seen_bids:
                continue

            title = str(item.get("Title") or item.get("title") or item.get("Subject") or item.get("subject") or "").strip()
            if SANCTION_TITLE_KEYWORD not in title and "制裁公告" not in title and "懲處名單" not in title:
                continue

            raw_date = str(
                item.get("startDate")
                or item.get("StartDate")
                or item.get("Dt")
                or item.get("dt")
                or item.get("CreateDate")
                or item.get("createDate")
                or item.get("Date")
                or item.get("date")
                or item.get("PublishDate")
                or ""
            )
            pub_date = normalize_date_str(raw_date)
            if not pub_date:
                LOGGER.warning("Could not parse publication date from bulletin item: %r", item)
                continue

            url = f"{OFFICIAL_ORIGIN}/bulletin?Bid={bid}"
            headers.append(
                BulletinHeader(
                    bid=bid,
                    title=title,
                    publication_date=pub_date,
                    url=url,
                )
            )
            seen_bids.add(bid)

    return headers


class _SanctionTableHTMLParser(HTMLParser):
    """HTML parser extracting table rows and pairing columns (1/2, 3/4, 5/6)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.current_cell_text: list[str] = []
        self.current_row_cells: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self.in_table = True
        elif tag_lower == "tr":
            self.in_row = True
            self.current_row_cells = []
        elif tag_lower in ("td", "th"):
            self.in_cell = True
            self.current_cell_text = []
        elif tag_lower == "br" and self.in_cell:
            self.current_cell_text.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self.in_table = False
        elif tag_lower == "tr":
            self.in_row = False
            if self.current_row_cells:
                self.rows.append(self.current_row_cells)
            self.current_row_cells = []
        elif tag_lower in ("td", "th"):
            self.in_cell = False
            raw_text = "".join(self.current_cell_text)
            cleaned = html.unescape(raw_text).replace("\u00a0", " ").strip()
            self.current_row_cells.append(cleaned)
            self.current_cell_text = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.current_cell_text.append(data)


_HEADER_KEYWORDS = {"角色名稱", "角色名字", "遊戲帳號", "暱稱", "制裁結果", "處分內容", "處分結果", "懲處原因", "違規原因"}


def _is_header_or_empty(text: str) -> bool:
    cleaned = re.sub(r"\s+", "", text)
    return not cleaned or cleaned in _HEADER_KEYWORDS


def parse_sanction_html_table(html_content: str) -> list[SanctionEntry]:
    """Parse announcement HTML table and extract (masked_name, result) pairs.
    
    Pairs columns 1/2, 3/4, 5/6 across all table rows.
    Returns deduplicated SanctionEntry list maintaining original encounter order.
    """
    if not html_content or not html_content.strip():
        return []

    parser = _SanctionTableHTMLParser()
    parser.feed(html_content)

    entries: list[SanctionEntry] = []
    seen: set[tuple[str, str]] = set()

    for row in parser.rows:
        # Pair cells (0, 1), (2, 3), (4, 5)
        for col_idx in range(0, len(row) - 1, 2):
            masked_name = row[col_idx].strip()
            result = row[col_idx + 1].strip()

            if _is_header_or_empty(masked_name) or _is_header_or_empty(result):
                continue

            pair = (masked_name, result)
            if pair not in seen:
                seen.add(pair)
                entries.append(SanctionEntry(masked_name=masked_name, result=result))

    return entries


def parse_bulletin_detail_json(raw_bytes: bytes, bid: int) -> tuple[str, str, str, list[SanctionEntry]]:
    """Parse BulletinDetail API response.
    
    Returns (title, publication_date, url, entries).
    Raises ValueError if response or table cannot be parsed properly.
    """
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("utf-8", errors="replace")

    data = json.loads(text)
    
    # Official BulletinDetail content is in data.myDataSet.table.content or data.data.content etc.
    content_html = ""
    title = ""
    raw_date = ""

    table_data = None
    if isinstance(data, dict):
        inner = data.get("data") if isinstance(data.get("data"), dict) else data
        my_data_set = inner.get("myDataSet") or inner.get("MyDataSet") or data.get("myDataSet") or data.get("MyDataSet")
        if isinstance(my_data_set, dict):
            table_data = my_data_set.get("table") or my_data_set.get("Table")
        if table_data is None:
            table_data = inner.get("table") or inner.get("Table") or inner.get("data") or inner.get("Data") or inner

    if isinstance(table_data, list) and len(table_data) > 0:
        row = table_data[0]
        if isinstance(row, dict):
            content_html = str(row.get("Content") or row.get("content") or "")
            title = str(row.get("Title") or row.get("title") or row.get("Subject") or row.get("subject") or "")
            raw_date = str(
                row.get("startDate")
                or row.get("StartDate")
                or row.get("Dt")
                or row.get("dt")
                or row.get("CreateDate")
                or row.get("createDate")
                or ""
            )
    elif isinstance(table_data, dict):
        content_html = str(table_data.get("Content") or table_data.get("content") or "")
        title = str(table_data.get("Title") or table_data.get("title") or table_data.get("Subject") or table_data.get("subject") or "")
        raw_date = str(
            table_data.get("startDate")
            or table_data.get("StartDate")
            or table_data.get("Dt")
            or table_data.get("dt")
            or table_data.get("CreateDate")
            or table_data.get("createDate")
            or ""
        )

    if not content_html:
        raise ValueError(f"No content HTML found in bulletin detail for Bid {bid}")

    pub_date = normalize_date_str(raw_date)
    entries = parse_sanction_html_table(content_html)

    # If the announcement title indicates sanction bulletin, but 0 entries parsed, it is a parse failure
    if SANCTION_TITLE_KEYWORD in title and not entries:
        raise ValueError(f"Bulletin {bid} title matched {SANCTION_TITLE_KEYWORD!r} but parsed 0 table entries")

    url = f"{OFFICIAL_ORIGIN}/bulletin?Bid={bid}"
    return title, pub_date, url, entries
