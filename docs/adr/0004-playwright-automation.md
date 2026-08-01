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

## Consequences

- **優點**:
  - 100% 相容 SurveyCake 前端 JavaScript 渲染與 DOM 操作。
  - 對驗證碼具備良好的容錯機制。
- **缺點**:
  - 需要安裝 Playwright Chromium driver（可包含在打包發行中或自動下載）。
