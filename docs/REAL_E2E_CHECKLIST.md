# 真實環境驗證清單

這份清單把 mock 測試與真實環境驗證分開。不要把測試 fixture、使用者錄影目錄或使用者設定檔混用。

## 1. 自動化測試邊界

- [x] `cd web; pnpm test`：React UI、mock PyWebView API、歷史連結、Drive 狀態、設定 rollback、剪輯路徑、提交失敗保留表單。
- [x] `cd web; pnpm run test:types`：React 測試與 production source 型別。
- [x] `uv run pytest`：後端合約、錄影真實補幀、WASAPI 音訊 fallback、DPAPI 邊界、SurveyCake 填表、雙區域 OCR、白名單過濾、全域熱鍵、onedir 執行檔資源路徑。
- [x] `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`：React production build + PyInstaller onedir + 真實 OAuth client 資源檢查。
- [x] `uv run python scripts/verify_release_bundle.py --launch-smoke`：不開 GUI、不呼叫第三方服務的 frozen bundle smoke。

## 第三方服務 smoke

這些步驟會產生外部副作用，不能放入一般測試。先在 PowerShell 設定明確的執行閘門：

```powershell
$env:MAPLE_REPORTER_REAL_E2E = "1"
```

Google Drive（若尚未有有效 token，再加 `--allow-oauth` 開啟互動 OAuth）：

```powershell
uv run python scripts/real_e2e_smoke.py gdrive --allow-oauth
```

Discord：

```powershell
$env:MAPLE_REPORTER_E2E_DISCORD_WEBHOOK = "https://discord.com/api/webhooks/..."
uv run python scripts/real_e2e_smoke.py discord
```

SurveyCake／Gamania 送出（不可逆，必須另外加 `--allow-submit`）：

```powershell
$env:MAPLE_REPORTER_E2E_SUSPECT_ID = "由測試者指定的帳號"
$env:MAPLE_REPORTER_E2E_MAP = "由測試者指定的地圖"
$env:MAPLE_REPORTER_E2E_EVIDENCE_URL = "https://..."
uv run python scripts/real_e2e_smoke.py surveycake --allow-submit --headless
```

## Windows 實機手動檢查

- [ ] 指定真實 MapleStory Classic 視窗，按 UI 按鈕與兩組全域快捷鍵各錄影一次。
- [ ] 開啟／關閉錄音，確認錄影可回放且音訊來源正確。
- [ ] 用含角色 ID／地圖的真實畫面確認 OCR，並各測試 ID／地圖開關關閉。
- [ ] 循環錄影啟動、儲存、剪輯、還原；確認提交使用剪輯後檔案。
- [ ] 在未授權 Drive、Discord 未設定、Drive／Discord 上傳失敗時確認錯誤可重試。
- [ ] 歷史紀錄確認真實 URL 可開啟與複製，清除後重新載入仍為空。
- [ ] Frameless 視窗拖曳、四邊／四角 resize、Windows Snap、工作列名稱與圖示。

完成第三方或硬體項目時，請記錄日期、Windows／遊戲版本與結果；不要把 OAuth token、Webhook 或真實帳號寫入 repository。
