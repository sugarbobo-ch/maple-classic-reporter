# Maple Classic Reporter 文件索引

## 主要文件

- [README.md](../README.md)：安裝、使用、發佈與資料安全說明。
- [CONTEXT.md](../CONTEXT.md)：目前版本、領域術語與架構背景。
- [UPDATES.md](UPDATES.md)：自動更新介面、Release notes、差分／完整包選擇、簽章、套用進度與暫存清理流程。
- [REAL_E2E_CHECKLIST.md](REAL_E2E_CHECKLIST.md)：Windows 實機與發行 bundle 驗收清單。
- [WINDOW_DPI_DRAG_BEHAVIOR.md](WINDOW_DPI_DRAG_BEHAVIOR.md)：混合 DPI 拖曳與無框視窗行為契約。

## 架構決策

`adr/` 保存主要 Architecture Decision Records，包括 PyWebView、OCR、Playwright、Google Drive OAuth 與非同步工作流程。

## Release notes

- [v2.0.0](releases/v2.0.0.md)：正式版，包含可選擇的錄音來源、內建 updater、檔案級差分、簽章 manifest、更新狀態與 Release notes 顯示。
- [v2.0.0-pre](releases/v2.0.0-pre.md)：2.0.0 預覽版與 PyWebView + React UI 架構升級。
- [v1.1.2](releases/v1.1.2.md)
- [v1.1.1](releases/v1.1.1.md)
- [v1.1.0](releases/v1.1.0.md)

`archive/` 保存歷史規格與交接文件。除非正在追查歷史行為，否則以目前程式碼、README、CONTEXT 與本索引為準。
