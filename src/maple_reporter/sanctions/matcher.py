"""Strict Unicode NFC mask matcher and history evaluation logic."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from maple_reporter.sanctions.models import BulletinDetail, SanctionEntry

try:
    from zoneinfo import ZoneInfo
    TAIPEI_TZ = ZoneInfo("Asia/Taipei")
except Exception:
    from datetime import timezone, timedelta
    TAIPEI_TZ = timezone(timedelta(hours=8), name="Asia/Taipei")

LOGGER = logging.getLogger(__name__)


def normalize_nfc(text: str) -> str:
    """Normalize text using Unicode NFC and strip whitespace."""
    if not text:
        return ""
    return unicodedata.normalize("NFC", text).strip()


def build_mask_regex_pattern(masked_name: str) -> str:
    """Convert a masked name with '*' into a strict exact-length regex pattern.
    
    Each '*' corresponds to exactly one Unicode code point (character).
    All other characters are escaped.
    """
    normalized_mask = normalize_nfc(masked_name)
    parts = []
    for char in normalized_mask:
        if char == "*":
            parts.append(".")
        else:
            parts.append(re.escape(char))
    return "^" + "".join(parts) + "$"


def match_masked_name(full_name: str, masked_name: str) -> bool:
    """Check if a full character ID matches a masked announcement name.
    
    Rules:
    - Unicode NFC normalized.
    - Case sensitive.
    - Each '*' represents exactly one Unicode code point.
    - Total character length must match exactly.
    """
    norm_full = normalize_nfc(full_name)
    norm_mask = normalize_nfc(masked_name)

    if not norm_full or not norm_mask:
        return False

    if len(norm_full) != len(norm_mask):
        return False

    pattern = build_mask_regex_pattern(norm_mask)
    return bool(re.fullmatch(pattern, norm_full))


def parse_taiwan_date(raw_time_str: str) -> str | None:
    """Extract YYYY-MM-DD from various timestamp formats or parse ISO strings."""
    if not raw_time_str or not isinstance(raw_time_str, str):
        return None

    raw = raw_time_str.strip()
    # Simple regex search for YYYY-MM-DD or YYYY/MM/DD
    match = re.search(r"\b(\d{4})[-/](\d{2})[-/](\d{2})\b", raw)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    # Try ISO format parsing
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            # Assume Taipei time if naive
            dt = dt.replace(tzinfo=TAIPEI_TZ)
        else:
            dt = dt.astimezone(TAIPEI_TZ)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


@dataclass(frozen=True)
class MatchCandidate:
    bulletin: BulletinDetail
    entry: SanctionEntry


def find_matching_bulletin(
    suspect_id: str,
    report_date: str,
    bulletins: list[BulletinDetail],
) -> MatchCandidate | None:
    """Find all matching entries for suspect_id in bulletins with publication_date >= report_date.
    
    If multiple matches are found, picks the latest publication_date; if tied, highest numerical Bid.
    """
    norm_id = normalize_nfc(suspect_id)
    if not norm_id:
        return None

    candidates: list[MatchCandidate] = []

    for bulletin in bulletins:
        if report_date and bulletin.publication_date < report_date:
            continue

        for entry in bulletin.entries:
            if match_masked_name(norm_id, entry.masked_name):
                # Any non-empty sanction result counts as banned
                if entry.result.strip():
                    candidates.append(MatchCandidate(bulletin=bulletin, entry=entry))

    if not candidates:
        return None

    # Sort candidates by publication_date descending, then bid descending
    candidates.sort(
        key=lambda c: (c.bulletin.publication_date, c.bulletin.bid),
        reverse=True,
    )
    return candidates[0]
