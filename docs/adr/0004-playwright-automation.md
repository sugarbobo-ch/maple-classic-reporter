# ADR 0004: Form Automation Strategy via Playwright

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

官方回報表單 (`https://forms.gamania.com/s/eLGg4`) 為 SurveyCake Enterprise 動態 SPA 網頁，可能包含動態防偽 Token 或 Captcha 驗證機制。

## Decision

採用 **Playwright (Python)** 執行表單自動填寫與送出：
1. 軟體開啟 Playwright Chromium 實例，導向 SurveyCake 回報頁面。
2. 自動填入「外掛角色 ID」、「選擇伺服器」、「地圖名稱」、「備註說明」及上傳成功後產生的事證連結。
3. 預設執行背景填表與送出；若偵測到 reCAPTCHA / Captcha 驗證碼，視窗會自動顯示以允許使用者手動點擊驗證，完成後自動送出並傳回結果。
4. Windows 發行版將 Playwright driver 與 Chromium 一起封裝於單一 EXE。啟動時優先使用內嵌瀏覽器；若封裝檔損壞或遺失，才嘗試使用使用者的 Playwright cache 下載，兩者都失敗時顯示可複製的完整錯誤資訊與官方下載網址。

## Consequences

- **優點**:
  - 100% 相容 SurveyCake 前端 JavaScript 渲染與 DOM 操作。
  - 對驗證碼具備良好的容錯機制。
- **缺點**:
  - 內嵌 Chromium 使單一 EXE 約 400MB，首次啟動也需要解壓較大的執行資源。
  - 若內嵌瀏覽器與 cache 都不可用，使用者仍需依錯誤視窗提供的網址處理瀏覽器元件問題。
