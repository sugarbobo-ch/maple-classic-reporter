import time
from typing import Dict, Tuple
from playwright.sync_api import sync_playwright

FORM_URL = "https://forms.gamania.com/s/eLGg4"

def submit_gamania_report(
    suspect_id: str,
    server_name: str,
    map_name: str,
    note: str,
    evidence_url: str,
    headless: bool = False
) -> Tuple[bool, str]:
    """
    Automate filling out Gamania MapleStory Classic report form using Playwright.
    Returns (success_boolean, status_message).
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()

            page.goto(FORM_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_selector("form, #survey, [data-subject-id]", timeout=15000)

            # 1. Fill suspect ID (Text input)
            # Find subject container containing "角色ID" or first text subject
            id_input = page.locator('input[type="text"]').nth(0)
            if id_input.is_visible():
                id_input.fill(suspect_id)

            # 2. Select Server (Radio button: 雪吉拉 or 菇菇寶貝)
            # Find radio option containing server_name
            server_label = page.locator(f'label:has-text("{server_name}"), div:has-text("{server_name}")').last
            if server_label and server_label.is_visible():
                server_label.click()

            # 3. Fill Map Name (Text input)
            map_input = page.locator('input[type="text"]').nth(1)
            if map_input.is_visible():
                map_input.fill(map_name)

            # 4. Fill Note (Text input)
            note_input = page.locator('input[type="text"]').nth(2)
            if note_input.is_visible():
                note_input.fill(note)

            # SurveyCake can reorder text fields; the evidence field is a URL input.
            url_input = page.locator('input[type="url"]')
            if url_input.count() != 1 or not url_input.is_visible():
                browser.close()
                return False, "找不到唯一的事證網址欄位，已取消送出。"
            url_input.fill(evidence_url)

            # Wait brief moment before submit
            time.sleep(1)

            # Find Submit Button
            submit_btn = page.locator('button:has-text("送出"), [role="button"]:has-text("送出"), div:has-text("送出")').last
            if submit_btn and submit_btn.is_visible():
                submit_btn.click()
                time.sleep(3)
                browser.close()
                return True, f"外掛 ID「{suspect_id}」成功送出回報！"
            else:
                browser.close()
                return False, "無法在表單找到「送出」按鈕。"
    except Exception as e:
        return False, f"Playwright 表單發送失敗: {str(e)}"
