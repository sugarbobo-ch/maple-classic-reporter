"""Backward-compatible OCR facade.

Provider adapters, image preprocessing, and candidate ranking live in separate
modules. This facade keeps the local OCR functions used by the existing UI
stable.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

import numpy as np
from PIL import Image

from maple_reporter.ocr.candidate_ranker import (
    CandidateObservation,
    EXACT_NOISE_TOKENS,
    SUBSTRING_NOISE_KEYWORDS,
    is_map_noise,
    is_valid_suspect_id,
    rank_candidate_observations,
    select_most_supported_map,
)
from maple_reporter.ocr.image_preprocessing import (
    bbox_center_y,
    clean_map_ocr_text,
    crop_minimap_region,
    normalize_ocr_text,
)
from maple_reporter.ocr.map_catalog import best_map_name_match, resolve_map_name
from maple_reporter.ocr.ocr_providers import (
    HAS_RAPID_OCR,
    HAS_WINSDK,
    RAPID_OCR_ENGINE,
    recognize_text_from_image as _provider_recognize_text_from_image,
)


LOGGER = logging.getLogger(__name__)
_MAP_LABELS = ("小地圖", "小地畫", "小地图", "小地画")
_MAP_NOISE = [*_MAP_LABELS, "NEWS", "NEW", "Pup", "Pdn", "HP", "MP", "EXP", "LV"]
_GUILD_MEDAL_EXCLUSION_PX = 60
_BOTTOM_UI_CROP_Y = 0.91


def recognize_text_from_image(pil_image: Image.Image) -> str:
    return _provider_recognize_text_from_image(pil_image)


def _clean_map_ocr_text(text: str) -> str:
    """Compatibility alias for the deterministic map-text normalizer."""

    return clean_map_ocr_text(text)


def _bbox_cy(bbox) -> float:
    return bbox_center_y(bbox)


def _ocr_result(engine, image: Image.Image):
    result = engine(np.asarray(image))
    if isinstance(result, tuple):
        return result[0]
    return result


def _downscale_for_ocr(image: Image.Image, max_dim: int = 1920) -> tuple[Image.Image, float]:
    """Downscale large images for faster full-frame OCR and return the scale factor."""
    w, h = image.size
    if max_dim <= 0 or (w <= max_dim and h <= max_dim):
        return image, 1.0
    if w >= h:
        new_w = max_dim
        scale = max_dim / float(w)
        new_h = max(1, int(h * scale))
    else:
        new_h = max_dim
        scale = max_dim / float(h)
        new_w = max(1, int(w * scale))
    return image.resize((new_w, new_h), Image.Resampling.BILINEAR), scale



def _is_map_label(text: str) -> bool:
    return any(label in text for label in _MAP_LABELS)


def _select_map_line(lines: list[tuple[str, float]]) -> str:
    """Pick the actual map line from the mini-map text rows.

    MapleStory normally renders a broad region on the first row and the map
    name on the next row.  OCR can miss either row, though, so a single row is
    still a valid map candidate.  Prefer the offline catalogue when possible
    and retain the OCR text for hidden maps that are not in the catalogue.
    """

    if not lines:
        return ""

    candidate_lines = lines[1:] if len(lines) >= 2 else lines
    catalogue_matches = []
    for index, (text, score) in enumerate(candidate_lines):
        candidate, similarity = best_map_name_match(text)
        if candidate and similarity >= 0.76:
            catalogue_matches.append((candidate, similarity, score, index))

    if catalogue_matches:
        return max(
            catalogue_matches,
            key=lambda item: (item[1], item[2], -item[3]),
        )[0]

    # Keep support for maps that are not yet in map_names_zh.json.  The first
    # row after the region is the map title; later rows can be extra UI text.
    return candidate_lines[0][0]


def recognize_map_name_from_image_list(
    pil_images: List[Image.Image],
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Recognize the mini-map title and vote across keyframes."""

    if not HAS_RAPID_OCR or RAPID_OCR_ENGINE is None:
        return ""

    detections: list[str] = []
    total_frames = len(pil_images)
    for frame_index, image in enumerate(pil_images, 1):
        if on_progress:
            try:
                on_progress(frame_index, total_frames)
            except Exception:
                pass
        if image.mode != "RGB":
            image = image.convert("RGB")
        try:
            results = _ocr_result(RAPID_OCR_ENGINE, crop_minimap_region(image)) or []
        except Exception as error:
            LOGGER.debug("RapidOCR 小地圖裁切辨識失敗 (%s)", type(error).__name__)
            continue

        sorted_results = sorted(results, key=lambda item: _bbox_cy(item[0]))
        label_y = None
        for bbox, raw_text, score in sorted_results:
            text = _clean_map_ocr_text(raw_text)
            center_y = _bbox_cy(bbox)
            if _is_map_label(text):
                label_y = center_y
                continue
            if is_map_noise(text, _MAP_NOISE) or not (0.40 <= score and 2 <= len(text) <= 22):
                continue

        if label_y is not None:
            lines: list[tuple[str, float]] = []
            for bbox, raw_text, score in sorted_results:
                text = _clean_map_ocr_text(raw_text)
                center_y = _bbox_cy(bbox)
                # OCR boxes can be close together on small captures.
                if center_y <= label_y + 2 or is_map_noise(text, _MAP_NOISE):
                    continue
                if score < 0.40 or not (2 <= len(text) <= 22):
                    continue
                lines.append((text, float(score)))
            actual_text = _select_map_line(lines)
            if actual_text:
                detections.append(actual_text)
                match, sim = best_map_name_match(actual_text)
                if match and sim >= 0.85:
                    return match
                return actual_text
            continue

        for bbox, raw_text, score in sorted_results:
            text = _clean_map_ocr_text(raw_text)
            if is_map_noise(text, _MAP_NOISE) or score < 0.45:
                continue
            if 2 <= len(text) <= 22:
                candidate = resolve_map_name(text)
                if candidate:
                    return candidate

        if detections:
            return detections[0]

    # Hidden mini-maps may show a transition banner elsewhere. Only accept a
    # strict offline catalogue match in that fallback region.
    if not detections and len(pil_images) > 0:
        for image in pil_images[:2]:
            if image.mode != "RGB":
                image = image.convert("RGB")
            try:
                results = _ocr_result(RAPID_OCR_ENGINE, image) or []
                for bbox, raw_text, score in results:
                    text = _clean_map_ocr_text(raw_text)
                    xs = [point[0] for point in bbox]
                    ys = [point[1] for point in bbox]
                    if max(xs) < image.width * 0.38 and max(ys) < image.height * 0.28:
                        continue
                    if is_map_noise(text, _MAP_NOISE) or score < 0.55:
                        continue
                    if not (2 <= len(text) <= 22):
                        continue
                    candidate, similarity = best_map_name_match(text)
                    if candidate and similarity >= 0.88:
                        detections.append(candidate)
                        return candidate
            except Exception as error:
                LOGGER.debug("RapidOCR 全畫面地圖候選失敗 (%s)", type(error).__name__)

    return select_most_supported_map(detections)


def recognize_candidates_from_image_list(
    pil_images: List[Image.Image],
    detected_map_name: str = "",
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> List[str]:
    """Extract, filter, and rank player ID candidates from keyframes."""

    observations: list[CandidateObservation] = []
    total_frames = len(pil_images)
    for frame_index, raw_image in enumerate(pil_images, 1):
        if on_progress:
            try:
                on_progress(frame_index, total_frames)
            except Exception:
                pass
        image, scale = _downscale_for_ocr(raw_image, max_dim=1920)
        if image.mode != "RGB":
            image = image.convert("RGB")
        width, height = image.size
        is_snippet = width < 600 or height < 500
        frame_entries: list[tuple[str, float, float, float, float]] = []

        if HAS_RAPID_OCR and RAPID_OCR_ENGINE:
            try:
                # Slices for gameplay candidate extraction
                scan_regions: list[tuple[int, int, int, int, float]] = [
                    (0, 0, width, height, 1.0),
                ]
                if not is_snippet and (width <= 1600 or height <= 900):
                    scan_regions.extend([
                        (0, 0, int(width * 0.55), int(height * 0.55), 1.3),
                        (int(width * 0.45), 0, width, int(height * 0.55), 1.3),
                        (0, int(height * 0.40), int(width * 0.55), int(height * _BOTTOM_UI_CROP_Y), 1.5),
                        (int(width * 0.45), int(height * 0.40), width, int(height * _BOTTOM_UI_CROP_Y), 1.3),
                    ])

                for x1, y1, x2, y2, scan_scale in scan_regions:
                    sub = image.crop((x1, y1, x2, y2))
                    if scan_scale != 1.0:
                        sub = sub.resize(
                            (int(sub.width * scan_scale), int(sub.height * scan_scale)),
                            Image.Resampling.LANCZOS,
                        )
                    results = _ocr_result(RAPID_OCR_ENGINE, sub) or []
                    for bbox, raw_text, score in results:
                        text = normalize_ocr_text(raw_text)
                        xs = [float(point[0]) / scan_scale + x1 for point in bbox]
                        ys = [float(point[1]) / scan_scale + y1 for point in bbox]
                        center_x = sum(xs) / len(xs)
                        center_y = sum(ys) / len(ys)
                        y_bottom = max(ys)
                        if not is_snippet:
                            if center_x < width * 0.15 and center_y < height * 0.20:
                                continue
                            if center_y > height * _BOTTOM_UI_CROP_Y:
                                continue
                        if detected_map_name and detected_map_name in text:
                            continue
                        if score >= (0.25 if is_snippet else 0.35) and is_valid_suspect_id(text):
                            frame_entries.append((text, center_x, center_y, y_bottom, float(score)))
            except Exception as error:
                LOGGER.debug("RapidOCR 玩家候選辨識失敗 (%s)", type(error).__name__)

        def in_guild_or_medal_zone(center_x: float, center_y: float) -> bool:
            for _, id_x, _, id_bottom, _ in frame_entries:
                if center_y > id_bottom and center_y <= id_bottom + _GUILD_MEDAL_EXCLUSION_PX:
                    if abs(center_x - id_x) <= width * 0.15:
                        return True
            return False

        for text, center_x, center_y, _, score in frame_entries:
            if not in_guild_or_medal_zone(center_x, center_y):
                observations.append(CandidateObservation(text, score, frame_index))
                # Disambiguate common pixel font rendering confusions
                if "凱" in text or "凯" in text:
                    cand_pa = text.replace("凱", "趴").replace("凯", "趴")
                    if is_valid_suspect_id(cand_pa):
                        observations.append(CandidateObservation(cand_pa, score + 0.05, frame_index))
                if any(kw in text for kw in ("間門", "同門", "閒門")):
                    cand_door = text.replace("間門", "開門").replace("同門", "開門").replace("閒門", "開門")
                    if is_valid_suspect_id(cand_door):
                        observations.append(CandidateObservation(cand_door, score + 0.05, frame_index))

        # Windows OCR fallback on game view region without expensive micro-patch loop
        if not observations and HAS_WINSDK and width > 150 and height > 150:
            try:
                crop_box = (
                    int(width * 0.05),
                    int(height * 0.15),
                    int(width * 0.95),
                    int(height * _BOTTOM_UI_CROP_Y),
                )
                cropped_img = image.crop(crop_box)
                full_text = recognize_text_from_image(cropped_img)
                for line in full_text.splitlines():
                    cand = normalize_ocr_text(line.strip())
                    if cand and is_valid_suspect_id(cand) and cand != detected_map_name:
                        observations.append(CandidateObservation(cand, 0.75, frame_index))
            except Exception as error:
                LOGGER.debug("Windows OCR 備用語法失敗 (%s)", type(error).__name__)

    return rank_candidate_observations(observations)


__all__ = [
    "EXACT_NOISE_TOKENS",
    "HAS_RAPID_OCR",
    "HAS_WINSDK",
    "RAPID_OCR_ENGINE",
    "SUBSTRING_NOISE_KEYWORDS",
    "_bbox_cy",
    "_clean_map_ocr_text",
    "is_valid_suspect_id",
    "recognize_candidates_from_image_list",
    "recognize_map_name_from_image_list",
    "recognize_text_from_image",
]
