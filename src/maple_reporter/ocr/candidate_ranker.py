"""Candidate validation and deterministic ranking for OCR observations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

EXACT_NOISE_TOKENS = {
    "hp", "mp", "exp", "lv", "level", "ch", "news", "new", "pup", "pdn",
    "0/", "1/", "2/", "3/", "4/", "5/", "(+", "（+", "auto",
}

SUBSTRING_NOISE_KEYWORDS = {
    "頻道", "選單", "設定", "背包", "商城", "技能", "任務", "新楓之谷", "經典版",
    "surveycake", "gamania", "橘子", "經驗值", "得到", "組隊", "地圖", "商場",
    "目錄", "拍賣", "兔子", "勳章", "動章", "徽章", "稱號", "冒險家",
    "指引", "公會", "auto",
}


@dataclass(frozen=True)
class CandidateObservation:
    text: str
    confidence: float
    frame_index: int


def is_valid_suspect_id(text: str) -> bool:
    """Check whether OCR text can plausibly be a player ID."""

    value = str(text or "").strip()
    if not (2 <= len(value) <= 12) or value.isdigit():
        return False
    if any(char in value for char in "/+::：[]()（）"):
        return False
    lowered = value.lower()
    if lowered in EXACT_NOISE_TOKENS:
        return False
    return not any(keyword in lowered for keyword in SUBSTRING_NOISE_KEYWORDS)


def rank_candidate_observations(
    observations: Iterable[CandidateObservation],
) -> list[str]:
    """Rank repeated observations by frame frequency, then confidence.

    A candidate contributes at most once per frame. This makes a noisy OCR
    engine that repeats the same word in one image unable to outrank a name
    consistently found across several frames.
    """

    counts: Counter[str] = Counter()
    max_scores: dict[str, float] = {}
    seen: set[tuple[int, str]] = set()
    for observation in observations:
        text = str(observation.text).strip()
        if not is_valid_suspect_id(text):
            continue
        key = (int(observation.frame_index), text)
        if key in seen:
            continue
        seen.add(key)
        counts[text] += 1
        max_scores[text] = max(max_scores.get(text, 0.0), float(observation.confidence))

    return sorted(
        counts,
        key=lambda text: (-counts[text], -max_scores.get(text, 0.0), text.casefold()),
    )


def select_most_supported_map(detections: Iterable[str]) -> str:
    """Return the most frequent map detection with deterministic tie-breaking."""

    counts = Counter(str(value).strip() for value in detections if str(value).strip())
    if not counts:
        return ""
    return sorted(counts, key=lambda value: (-counts[value], value))[0]


def is_map_noise(text: str, noise_tokens: Iterable[str]) -> bool:
    value = str(text or "")
    return any(token in value for token in noise_tokens)


__all__ = [
    "CandidateObservation",
    "EXACT_NOISE_TOKENS",
    "SUBSTRING_NOISE_KEYWORDS",
    "is_map_noise",
    "is_valid_suspect_id",
    "rank_candidate_observations",
    "select_most_supported_map",
]
