import base64
import json
import requests
import io
import asyncio
from collections import Counter
from typing import List, Tuple
from PIL import Image
import cv2
import numpy as np
from maple_reporter.ocr.map_catalog import best_map_name_match, resolve_map_name

# ---------------------------------------------------------------------------
# Gemma unified: one API call -> both player IDs + map name
# ---------------------------------------------------------------------------

_GEMINI_MODEL = "gemma-4-31b-it"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def recognize_with_gemini_unified(
    pil_image: Image.Image, api_key: str
) -> Tuple[List[str], str]:
    """
    Single Gemma API call that returns BOTH player IDs and map name.
    Returns (ids_list, map_name_str). Falls back to ([], "") on error.
    """
    if not api_key:
        return [], ""

    try:
        buffer = io.BytesIO()
        pil_image.convert("RGB").save(buffer, format="JPEG", quality=85)
        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        url = f"{_GEMINI_BASE}/{_GEMINI_MODEL}:generateContent?key={api_key.strip()}"

        prompt = (
            "這是《新楓之谷：經典版》遊戲截圖。請分析並以 JSON 格式回傳以下兩項資訊：\n"
            "1. \"ids\": 畫面中所有玩家角色 ID 的陣列（忽略怪物、NPC、裝備、選單文字）。\n"
            "   注意：每個角色標籤由上到下為「角色ID → 公會名稱（若有）→ 勳章名稱（若有）」，"
            "   公會名稱和勳章名稱請勿列入 ids。\n"
            "2. \"map_name\": 畫面左上角小地圖方框內顯示的地圖名稱（中文）。"
            "   「小地圖」四個字是標籤，不是地圖名稱，請忽略。"
            "   若看不到地圖名稱請填空字串。\n\n"
            "只回傳純 JSON，範例：{\"ids\": [\"PlayerA\", \"PlayerB\"], \"map_name\": \"維多利亞島\"}"
        )

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                ]
            }]
        }
        headers = {"Content-Type": "application/json"}
        resp = requests.post(url, json=payload, headers=headers, timeout=12)

        if resp.status_code == 200:
            parts = (
                resp.json()
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])
            )
            reply = parts[0].get("text", "")
            if "{" in reply and "}" in reply:
                json_str = reply[reply.find("{"):reply.rfind("}") + 1]
                try:
                    data = json.loads(json_str)
                    raw_ids = data.get("ids", [])
                    ids = [
                        str(i).strip()
                        for i in raw_ids
                        if is_valid_suspect_id(str(i).strip())
                    ]
                    map_name = str(data.get("map_name", "")).strip().replace(" ", "")
                    _map_noise = ["小地圖", "小地畫", "null", "None", "undefined"]
                    if any(n in map_name for n in _map_noise) or len(map_name) > 25:
                        map_name = ""
                    return ids, map_name
                except Exception:
                    pass
    except Exception:
        pass
    return [], ""


def recognize_with_gemini_vision(pil_image: Image.Image, api_key: str) -> List[str]:
    """Backward-compatible wrapper - returns only the IDs list."""
    ids, _ = recognize_with_gemini_unified(pil_image, api_key)
    return ids


def recognize_map_name_with_gemini(pil_images: list, api_key: str) -> str:
    """Backward-compatible wrapper - returns only the map name string."""
    for img in pil_images[:2]:
        _, map_name = recognize_with_gemini_unified(img, api_key)
        if map_name:
            return map_name
    return ""


# ---------------------------------------------------------------------------
# WinSDK OCR (optional)
# ---------------------------------------------------------------------------
try:
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    HAS_WINSDK = True
except ImportError:
    HAS_WINSDK = False

# ---------------------------------------------------------------------------
# RapidOCR (primary local engine)
# ---------------------------------------------------------------------------
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPID_OCR_ENGINE = RapidOCR()
    HAS_RAPID_OCR = True
except Exception:
    RAPID_OCR_ENGINE = None
    HAS_RAPID_OCR = False


# ---------------------------------------------------------------------------
# Single-image text recognition (WinSDK path)
# ---------------------------------------------------------------------------
def recognize_text_from_image(pil_image: Image.Image) -> str:
    if not HAS_WINSDK:
        return ""
    try:
        return asyncio.run(_async_ocr(pil_image))
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Map name detection using RapidOCR (no API key required)
# Strategy: sort all bbox by Y -> find "小地圖" label -> take next valid row.
# ---------------------------------------------------------------------------
_MAP_NOISE = [
    "小地圖", "小地畫",
    "NEWS", "NEW", "Pup", "Pdn", "HP", "MP", "EXP", "LV"
]


def _clean_map_ocr_text(text: str) -> str:
    """Correct recurring MapleStory mini-map glyph substitutions only."""
    value = text.strip().replace(" ", "")
    # The compact mini-map font frequently loses 「練」 or reads it as 「辣」.
    value = value.replace("訓辣", "訓練").replace("訓場", "訓練場")
    # A trailing Roman numeral I is commonly recognised as an exclamation mark.
    if value.endswith(("!", "！")):
        value = f"{value[:-1]}Ⅰ"
    return value


def _bbox_cy(bbox) -> float:
    """Return center Y of an OCR bounding box."""
    return sum(pt[1] for pt in bbox) / len(bbox)


def recognize_map_name_from_image_list(pil_images: List[Image.Image]) -> str:
    """
    Recognize map name from the top-left mini-map region using RapidOCR.
    Algorithm:
      1. Crop top-left 38% x 28% of frame.
      2. Sort OCR results by center-Y (top to bottom).
      3. Use the actual second mini-map line, including unlisted hidden maps.
      4. When the mini-map is hidden, scan the whole frame for a high-confidence
         catalogue match (for example, a map-transition banner).
      5. Vote across frames so a single bad OCR result cannot overwrite the map.
    """
    if not HAS_RAPID_OCR or not RAPID_OCR_ENGINE:
        return ""

    detections = []
    for img in pil_images:
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        crop = img.crop((0, 0, int(w * 0.38), int(h * 0.28)))
        try:
            res, _ = RAPID_OCR_ENGINE(np.array(crop))
            if not res:
                continue

            sorted_res = sorted(res, key=lambda item: _bbox_cy(item[0]))
            label_y = None

            for bbox, text, score in sorted_res:
                txt = _clean_map_ocr_text(text)
                cy = _bbox_cy(bbox)

                if "小地圖" in txt or "小地畫" in txt:
                    label_y = cy
                    continue

                if any(n in txt for n in _MAP_NOISE):
                    continue
                if score < 0.40 or len(txt) < 2 or len(txt) > 22:
                    continue

            # The mini-map exposes a region line followed by the actual map
            # line. The second line is authoritative even for hidden maps that
            # are not yet present in the offline catalogue.
            if label_y is not None:
                lines: list[tuple[str, float]] = []
                for bbox, text, score in sorted_res:
                    txt = _clean_map_ocr_text(text)
                    cy = _bbox_cy(bbox)
                    if cy <= label_y + 12 or any(n in txt for n in _MAP_NOISE):
                        continue
                    if score < 0.40 or len(txt) < 2 or len(txt) > 22:
                        continue
                    lines.append((txt, float(score)))

                if len(lines) >= 2:
                    actual_map_text, _ = lines[1]
                    # Canonicalise only when the catalogue has a strong match;
                    # otherwise retain the OCR text so unlisted hidden maps
                    # can still be reviewed and selected by the user.
                    canonical = resolve_map_name(actual_map_text, minimum_score=0.86)
                    detections.append(canonical or actual_map_text)

                # Never reinterpret the first line (the broad region, such as
                # "維多利亞") as a map name when the second line is missing.
                continue

            # With no detected label, permit a catalogue match only. Never
            # return arbitrary OCR text (e.g. "小地图") as a map name.
            for bbox, text, score in sorted_res:
                txt = _clean_map_ocr_text(text)
                if any(n in txt for n in _MAP_NOISE):
                    continue
                if score >= 0.45 and 2 <= len(txt) <= 22:
                    candidate = resolve_map_name(txt)
                    if candidate:
                        detections.append(candidate)
                        break

        except Exception:
            pass
    # A hidden mini-map has no title to read in its usual top-left region. In
    # that case, a map title can still appear elsewhere in a frame (such as a
    # transition banner). Only accept a stricter catalogue match here so chat
    # text or ordinary UI labels cannot overwrite the editable map field.
    if not detections:
        for img in pil_images:
            if img.mode != "RGB":
                img = img.convert("RGB")
            try:
                res, _ = RAPID_OCR_ENGINE(np.array(img))
                if not res:
                    continue
                for bbox, text, score in res:
                    txt = _clean_map_ocr_text(text)
                    xs = [point[0] for point in bbox]
                    ys = [point[1] for point in bbox]
                    # This fallback is for a hidden mini-map only. Ignore the
                    # normal mini-map region so its broad area label cannot
                    # override the actual map line handled above.
                    if max(xs) < img.width * 0.38 and max(ys) < img.height * 0.28:
                        continue
                    if any(n in txt for n in _MAP_NOISE):
                        continue
                    if score < 0.55 or not (2 <= len(txt) <= 22):
                        continue
                    candidate, similarity = best_map_name_match(txt)
                    if candidate and similarity >= 0.88:
                        detections.append(candidate)
                        break
            except Exception:
                pass

    if not detections:
        return ""
    return Counter(detections).most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Noise keywords & ID validator
# ---------------------------------------------------------------------------
UI_NOISE_KEYWORDS = {
    "hp", "mp", "exp", "lv", "level", "ch", "頻道", "選單", "設定", "背包",
    "商城", "技能", "任務", "新楓之谷", "經典版", "surveycake", "gamania", "橘子",
    "news", "new", "pup", "pdn", "0/", "1/", "2/", "3/", "4/", "5/", "(+", "（+",
    "兔子", "法師", "目錄", "拍賣", "經驗值", "得到", "組隊", "地圖", "商場"
}


def is_valid_suspect_id(text: str) -> bool:
    """Check if candidate text complies with basic format rules."""
    s = text.strip()
    if not (2 <= len(s) <= 12):
        return False
    if s.isdigit():
        return False
    if any(c in s for c in ["/", "+", ":", "：", "[", "]", "(", ")", "（", "）"]):
        return False
    s_lower = s.lower()
    for kw in UI_NOISE_KEYWORDS:
        if kw in s_lower:
            return False
    return True


# ---------------------------------------------------------------------------
# Candidate ID recognition (RapidOCR + WinSDK fallback)
# ---------------------------------------------------------------------------
_GUILD_MEDAL_EXCLUSION_PX = 60
_BOTTOM_UI_CROP_Y = 0.78


def recognize_candidates_from_image_list(
    pil_images: List[Image.Image], detected_map_name: str = ""
) -> List[str]:
    """
    Recognize candidate player IDs from a list of keyframe Images using RapidOCR.
    Excludes top-left mini-map region, bottom UI bar, and detected map name.
    Post-filters guild/medal text below each ID bbox.
    Returns candidates ordered by frequency and confidence descending.
    """
    freq: dict = {}
    score_map: dict = {}

    for img in pil_images:
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        frame_seen: set = set()

        if HAS_RAPID_OCR and RAPID_OCR_ENGINE:
            try:
                np_img = np.array(img)
                result, _ = RAPID_OCR_ENGINE(np_img)
                if not result:
                    raise StopIteration

                all_items = []
                for item in result:
                    bbox, text, score = item
                    txt_clean = text.strip().replace(" ", "")
                    xs = [pt[0] for pt in bbox]
                    ys = [pt[1] for pt in bbox]
                    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
                    y_bottom = max(ys)

                    if cx < w * 0.32 and cy < h * 0.22:
                        continue
                    if cy > h * _BOTTOM_UI_CROP_Y:
                        continue
                    if detected_map_name and detected_map_name in txt_clean:
                        continue

                    all_items.append((txt_clean, cx, cy, y_bottom, score))

                candidate_entries = [
                    (txt, cx, cy, y_bottom, score)
                    for txt, cx, cy, y_bottom, score in all_items
                    if score >= 0.5 and is_valid_suspect_id(txt)
                ]

                def _in_guild_medal_zone(cx: float, cy: float) -> bool:
                    for _, id_cx, _, id_y_bottom, _ in candidate_entries:
                        if cy > id_y_bottom and cy <= id_y_bottom + _GUILD_MEDAL_EXCLUSION_PX:
                            if abs(cx - id_cx) <= w * 0.30:
                                return True
                    return False

                for txt, cx, cy, y_bottom, score in candidate_entries:
                    if _in_guild_medal_zone(cx, cy):
                        continue
                    if txt not in frame_seen:
                        frame_seen.add(txt)
                        freq[txt] = freq.get(txt, 0) + 1
                        score_map[txt] = max(score_map.get(txt, 0.0), float(score))

            except StopIteration:
                pass
            except Exception:
                pass

        if not freq and HAS_WINSDK:
            if w > 150 and h > 150:
                img_np = np.array(img)
                patch_w, patch_h = int(w * 0.18), int(h * 0.12)
                step_x, step_y = int(patch_w * 0.5), int(patch_h * 0.5)
                start_y, end_y = int(h * 0.15), int(h * _BOTTOM_UI_CROP_Y)
                start_x, end_x = int(w * 0.05), int(w * 0.95)
                for y in range(start_y, end_y, max(20, step_y)):
                    for x in range(start_x, end_x, max(30, step_x)):
                        sub_np = img_np[y:min(h, y + patch_h), x:min(w, x + patch_w)]
                        if sub_np.shape[0] < 20 or sub_np.shape[1] < 40:
                            continue
                        sub_pil = Image.fromarray(sub_np)
                        txt = recognize_text_from_image(sub_pil).strip()
                        if txt and is_valid_suspect_id(txt):
                            if txt not in frame_seen:
                                frame_seen.add(txt)
                                freq[txt] = freq.get(txt, 0) + 1
                                score_map[txt] = max(score_map.get(txt, 0.0), 0.8)

    return sorted(
        freq.keys(),
        key=lambda k: (freq[k], score_map.get(k, 0.0)),
        reverse=True
    )


# ---------------------------------------------------------------------------
# WinSDK async OCR helper
# ---------------------------------------------------------------------------
async def _async_ocr(pil_image: Image.Image) -> str:
    img_byte_arr = io.BytesIO()
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    pil_image.save(img_byte_arr, format="PNG")
    img_bytes = img_byte_arr.getvalue()

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(bytearray(img_bytes))
    await writer.store_async()
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        langs = list(OcrEngine.available_recognizer_languages)
        if langs:
            engine = OcrEngine.try_create_from_language(langs[0])

    if not engine:
        return ""

    ocr_result = await engine.recognize_async(bitmap)
    lines = [line.text for line in ocr_result.lines]
    raw_text = "".join(lines)
    cleaned = raw_text.replace(" ", "")
    return cleaned if cleaned else raw_text
