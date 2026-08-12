"""Backward-compatible OCR facade.

Provider adapters, image preprocessing, and candidate ranking live in separate
modules. This facade keeps the public functions used by the existing UI and
third-party integrations stable.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np
import requests
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
    recognize_with_gemini_unified as _provider_recognize_with_gemini_unified,
)


LOGGER = logging.getLogger(__name__)
_MAP_NOISE = ["小地圖", "小地畫", "NEWS", "NEW", "Pup", "Pdn", "HP", "MP", "EXP", "LV"]
_GUILD_MEDAL_EXCLUSION_PX = 60
_BOTTOM_UI_CROP_Y = 0.78


def recognize_with_gemini_unified(
    pil_image: Image.Image, api_key: str
) -> tuple[list[str], str]:
    ids, map_name = _provider_recognize_with_gemini_unified(
        pil_image, api_key, request_post=requests.post
    )
    return [candidate for candidate in ids if is_valid_suspect_id(candidate)], map_name


def recognize_with_gemini_vision(pil_image: Image.Image, api_key: str) -> List[str]:
    """Backward-compatible wrapper returning only player IDs."""

    ids, _ = recognize_with_gemini_unified(pil_image, api_key)
    return ids


def recognize_map_name_with_gemini(pil_images: list, api_key: str) -> str:
    """Backward-compatible wrapper returning only the map name."""

    for image in pil_images[:2]:
        _, map_name = recognize_with_gemini_unified(image, api_key)
        if map_name:
            return map_name
    return ""


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


def recognize_map_name_from_image_list(pil_images: List[Image.Image]) -> str:
    """Recognize the mini-map title and vote across keyframes."""

    if not HAS_RAPID_OCR or RAPID_OCR_ENGINE is None:
        return ""

    detections: list[str] = []
    for image in pil_images:
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
            if "小地圖" in text or "小地畫" in text:
                label_y = center_y
                continue
            if is_map_noise(text, _MAP_NOISE) or not (0.40 <= score and 2 <= len(text) <= 22):
                continue

        if label_y is not None:
            lines: list[tuple[str, float]] = []
            for bbox, raw_text, score in sorted_results:
                text = _clean_map_ocr_text(raw_text)
                center_y = _bbox_cy(bbox)
                if center_y <= label_y + 12 or is_map_noise(text, _MAP_NOISE):
                    continue
                if score < 0.40 or not (2 <= len(text) <= 22):
                    continue
                lines.append((text, float(score)))
            if len(lines) >= 2:
                actual_text = lines[1][0]
                detections.append(
                    resolve_map_name(actual_text, minimum_score=0.86) or actual_text
                )
            continue

        for bbox, raw_text, score in sorted_results:
            text = _clean_map_ocr_text(raw_text)
            if is_map_noise(text, _MAP_NOISE) or score < 0.45:
                continue
            if 2 <= len(text) <= 22:
                candidate = resolve_map_name(text)
                if candidate:
                    detections.append(candidate)
                    break

    # Hidden mini-maps may show a transition banner elsewhere. Only accept a
    # strict offline catalogue match in that fallback region.
    if not detections:
        for image in pil_images:
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
                        break
            except Exception as error:
                LOGGER.debug("RapidOCR 全畫面地圖候選失敗 (%s)", type(error).__name__)

    return select_most_supported_map(detections)


def recognize_candidates_from_image_list(
    pil_images: List[Image.Image], detected_map_name: str = ""
) -> List[str]:
    """Extract, filter, and rank player ID candidates from keyframes."""

    observations: list[CandidateObservation] = []
    for frame_index, image in enumerate(pil_images):
        if image.mode != "RGB":
            image = image.convert("RGB")
        width, height = image.size
        is_snippet = width < 600 or height < 500
        frame_entries: list[tuple[str, float, float, float, float]] = []

        if HAS_RAPID_OCR and RAPID_OCR_ENGINE:
            try:
                results = _ocr_result(RAPID_OCR_ENGINE, image) or []
                for bbox, raw_text, score in results:
                    text = normalize_ocr_text(raw_text)
                    xs = [float(point[0]) for point in bbox]
                    ys = [float(point[1]) for point in bbox]
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)
                    y_bottom = max(ys)
                    if not is_snippet:
                        if center_x < width * 0.32 and center_y < height * 0.22:
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
                    if abs(center_x - id_x) <= width * 0.30:
                        return True
            return False

        for text, center_x, center_y, _, score in frame_entries:
            if not in_guild_or_medal_zone(center_x, center_y):
                observations.append(CandidateObservation(text, score, frame_index))

        if not observations and HAS_WINSDK and width > 150 and height > 150:
            image_array = np.asarray(image)
            patch_w, patch_h = int(width * 0.18), int(height * 0.12)
            step_x, step_y = int(patch_w * 0.5), int(patch_h * 0.5)
            start_y, end_y = int(height * 0.15), int(height * _BOTTOM_UI_CROP_Y)
            start_x, end_x = int(width * 0.05), int(width * 0.95)
            for y in range(start_y, end_y, max(20, step_y)):
                for x in range(start_x, end_x, max(30, step_x)):
                    patch = image_array[y : min(height, y + patch_h), x : min(width, x + patch_w)]
                    if patch.shape[0] < 20 or patch.shape[1] < 40:
                        continue
                    text = recognize_text_from_image(Image.fromarray(patch)).strip()
                    if is_valid_suspect_id(text):
                        observations.append(CandidateObservation(text, 0.8, frame_index))

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
    "recognize_map_name_with_gemini",
    "recognize_text_from_image",
    "recognize_with_gemini_unified",
    "recognize_with_gemini_vision",
]
