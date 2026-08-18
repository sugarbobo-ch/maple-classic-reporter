# Maple Classic Auto Reporter - 文件目錄 (Documentation Index)

本目錄彙整《新楓之谷：經典版 自動外掛檢舉工具》的設計決策、發行紀錄、系統規格與歷史歸檔文件。

---

## 📂 目錄結構

```text
docs/
├── README.md                           # 本文件（文件導覽與索引）
├── REAL_E2E_CHECKLIST.md               # 真實環境端到端測試驗證清單
├── WINDOW_DPI_DRAG_BEHAVIOR.md         # 無框視窗、拖曳行為與多螢幕 DPI 規範
├── adr/                                # 架構決策記錄 (Architecture Decision Records)
│   ├── 0001-app-framework.md           # PySide6 + PyWebView 桌面架構
│   ├── 0002-ocr-engine.md              # RapidOCR ONNX 本機辨識引擎
│   ├── 0003-google-drive-integration.md# Google Drive OAuth 整合
│   ├── 0004-playwright-automation.md   # Playwright 表單填寫自動化
│   ├── 0005-workflow-and-video-recording.md # 錄影與工作流
│   ├── 0006-dual-region-ocr-and-auto-remember.md # 雙區域 OCR 與自動記憶
│   ├── 0007-ocr-preprocessing-and-multiframe-extraction.md # 影像預處理與抽幀
│   ├── 0008-ui-exclusion-and-client-area-ocr-filtering.md # UI 排除與過濾
│   ├── 0009-asynchronous-ocr-worker-thread.md # 非同步 OCR 背景工作線程
│   └── 0011-bundled-google-oauth-client.md # 內嵌 Google OAuth 用戶端
├── releases/                           # 各版本發布說明 (Release Notes)
│   ├── v1.1.0.md
│   ├── v1.1.1.md
│   ├── v1.1.2.md
│   └── v2.0.0-pre.md                   # 2.0.0-pre 預發布版本更新說明
└── archive/                            # 歷史與過渡性實作文件歸檔
    ├── EXPECTED_LAYOUT.md              # 早期 UI 版面規劃與重構對照
    ├── NEXT_AGENT_REFACTOR_HANDOFF.md  # 模組重構交接備忘
    ├── SANCTION_STATUS_IMPLEMENTATION_SPEC.md # 封鎖名單實作詳細規格
    ├── UI_PARITY_OPERATIONS.md         # UI 對齊與功能操作清單
    └── WEB_PYSIDE_PARITY.md            # Web / PySide6 雙介面過渡期對齊清單
```

---

## 📖 文件指引

- **專案概述與快速開始**：請參閱根目錄 [README.md](../README.md)。
- **領域模型與專有名詞**：請參閱根目錄 [CONTEXT.md](../CONTEXT.md)。
- **無框視窗與 DPI 拖曳規範**：請參閱 [WINDOW_DPI_DRAG_BEHAVIOR.md](WINDOW_DPI_DRAG_BEHAVIOR.md)。
- **E2E 驗證清單**：請參閱 [REAL_E2E_CHECKLIST.md](REAL_E2E_CHECKLIST.md)。
