# ADR 0006: Dual-Region OCR for Map Name & Character ID with Auto-Remember Defaults

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

在《新楓之谷：經典版》舉報外掛時，玩家需要填寫「外掛角色 ID」、「所在地圖」與「伺服器」。
手動輸入地圖名稱與角色 ID 繁瑣且易出錯，特別是外掛角色 ID 常包含特殊亂碼字元。
此外，玩家常在同一地圖與伺服器連續檢舉多名外掛，手動重複選擇預設值會降低舉報效率。

## Decision

1. **雙區塊 OCR (Dual-Region OCR)**：
   - 當玩家觸發截圖/舉報熱鍵（`F9`）時，系統透過 `pygetwindow` 自動定位「新楓之谷」遊戲視窗幾何座標。
   - 地圖名稱：自動擷取遊戲視窗左上角區域（寬 0~25%，高 0~15%）圖像進行 Windows Native OCR 辨識。
   - 角色 ID：透過半透明全螢幕遮罩 (`ScreenSnipperOverlay`) 由玩家拉框選取角色 ID 區域進行 OCR 辨識。

2. **自動記憶上一次使用紀錄 (Auto-remember Last Selection)**：
   - 系統自動將最後一次選擇與輸入的「伺服器」、「所在地圖」、「違規備註」、「錄影時長」持久化儲存於 `~/.maple_reporter/config.json`。
   - 下次啟動或開啟預覽視窗時自動預填上次選取之設定值。若地圖 OCR 辨識結果為空或雜訊，自動帶入上次預設地圖。

3. **預覽確認機制 (Report Preview Modal)**：
   - 雙區塊 OCR 完成後，彈出預覽視窗供玩家核對地圖名稱與角色 ID，確認無誤後才依使用者選定的目的地上傳，並以產生的連結進行 SurveyCake 自動填單。

## Consequences

- **優點**:
  - 玩家僅需拉框選取角色 ID，地圖名稱與上次設定自動帶入，大幅提升檢舉效率。
  - 預覽視窗確保送出給官方的資料 100% 精準。
- **缺點**:
  - 若遊戲 UI 樣式或地圖名稱標籤位置發生大幅異動，需更新左上角裁切比例。
