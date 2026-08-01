# ADR 0001: Application Framework & Package Management

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

我們需要為《新楓之谷：經典版》開發一款自動檢舉外掛的桌面工具。工具將開源並打包給一般玩家下載使用（提供雙擊即可運行的獨立 executable）。

## Decision

1. 使用 **Python 3.11+** 搭配 **PySide6 (Qt for Python)** 打造桌面 GUI 應用程式。
2. 使用 **uv** 作為 Python 包管理器與專案環境管理工具（以 `pyproject.toml` 管理依賴與打包腳本）。
3. 使用 **PyInstaller** 或 **Nuitka** 將應用程式打包為 Windows 單一可執行檔 (`.exe`)。

## Consequences

- **優點**:
  - Python 生態系具備成熟的 OCR、影像處理 (OpenCV/PIL) 與網路請求/自動化庫。
  - `uv` 提供極速的依賴安裝與環境建置。
  - PySide6 視覺效果良好，支援熱鍵、螢幕擷取 overlay 與異步線程 (QThread)。
- **缺點**:
  - 獨立打包後 `.exe` 檔案大小約 40MB-80MB。
