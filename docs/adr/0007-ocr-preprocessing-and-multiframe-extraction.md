# ADR 0007: OCR Image Preprocessing, Multi-Frame Candidate Extraction, and Custom FPS

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

遊戲《新楓之谷：經典版》的角色 ID 與地圖文字點陣小（12~14px），且背景複雜（遊戲地圖紋理、怪物、技能特效）。
直接使用原始視窗截圖送交 Windows Native OCR 常發生空字串或亂碼。
此外，在錄製違規短影片過程中，外掛角色常在畫面中移動，單一瞬間的截圖可能被技能遮擋或視窗邊緣遮擋。
同時，使用者需要能自訂錄影幀率 (FPS) 以兼顧影片順暢度與資源佔用。

## Decision

1. **OCR 圖像預處理管道 (Image Preprocessing Pipeline)**：
   - 使用 OpenCV 對裁切影像進行 2.5 倍影像放大（Bicubic 內插）。
   - 轉為灰階後，執行 Otsu 二值化與高對比降噪，過濾複雜背景，突出黑白文字線條。
   - 採用雙重辨識 (Dual-Pass Recognition)，若二值化結果為空則回退至放大原圖，大幅提昇識別率。

2. **多影格抽幀 OCR 與可編輯下拉選單 (Multi-Frame Video OCR & Candidate ComboBox)**：
   - 錄製違規短影片時，系統每隔固定間隔（如每 2 秒）抽出一張影格進行背景 OCR。
   - 將影格中辨識出的候選角色 ID 去重並整理為候選名單。
   - 在預覽視窗 (`ReportPreviewModal`) 的角色 ID 欄位提供「可編輯下拉選單 (`QComboBox`)」，允許玩家一鍵選擇識別出的候選 ID，亦可隨時打字修正。

3. **自訂錄影 FPS (Recording FPS)**：
   - 在主畫面介面提供 15 ~ 60 FPS 選項選單，預設 20 FPS，數值自動持久化至 `config.json`。

## Consequences

- **優點**:
  - 徹底解決小字體與複雜背景導致 OCR 偵測不到文字的問題。
  - 錄影期間多影格抽幀大幅提高捕獲移動中外掛角色的成功率。
  - 可編輯下拉選單兼具自動選擇的便利性與手動修改的彈性。
