# ADR 0008: UI Exclusion & Client Area OCR Noise Filtering

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

在《新楓之谷：經典版》遊戲視窗中，包含了 Windows 原生標題列（高度約 30~32px）、遊戲頂部 Mini-map 資訊欄（約佔 15%）、底部 HP/MP/EXP 血條與快捷列（約佔 15%）。
如果在短影片抽幀與 OCR 辨識時未排除這些 UI 區域，系統容易將視窗標題、傷害數字（如 `9999`）、技能名稱或 `HP/MP` 等介面文字誤識別為外掛角色 ID。

## Decision

1. **Win32 API 精準 Client Area 計算**：
   - 使用 Windows API `GetClientRect` 結合 `ClientToScreen` 計算遊戲視窗內部畫布的真實螢幕座標 (`left, top, width, height`)，動態排除標題列與視窗邊框。

2. **HUD 區域排除 (HUD Exclusions)**：
   - 對於短影片抽幀與區域辨識，自動排除頂部 Mini-map 區塊 (Y: 0~15%) 與底部快捷列區塊 (Y: 85%~100%)，將 OCR 辨識區域限制在中央戰鬥與角色移動區 (Y: 15%~85%)。

3. **候選角色 ID 語法與規則過濾**：
   - 剔除純數字串（例如傷害數字 `12345`）。
   - 剔除固定 UI 與系統關鍵字（如 `HP`, `MP`, `EXP`, `Lv`, `CH`, `頻道`, `選單`, `設定`, `背包`, `技能`）。
   - 限制角色 ID 有效字元長度在 3 ~ 12 字元之間。

## Consequences

- **優點**:
  - 徹底過濾標題列、血條與傷害數字干擾，使 OCR 名單乾淨且精準。
  - 玩家在下拉選單中看到的候選 ID 均為真正的角色名稱。
