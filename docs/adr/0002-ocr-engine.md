# ADR 0002: OCR Engine Selection

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

《新楓之谷：經典版》的外掛角色 ID 常包含特殊符號或亂碼，需要從遊戲螢幕截圖中準確辨識文字。

## Decision

採用 **Windows 原生 API (`Windows.Media.Ocr` / `winsdk`)** 作為文字辨識引擎。

## Consequences

- **優點**:
  - 零額外模型體積，利用 Windows 10/11 內建 OCR 資源。
  - 辨識速度極快（毫秒等級），支援繁體中文與英數符號。
  - 簡化 Packaging 與依賴安裝流程。
- **缺點**:
  - 僅限 Windows 作業系統（本工具主要針對 MapleStory 玩家，Windows 平台覆蓋率接近 100%）。
