# ADR 0011: Bundle the Google OAuth Desktop Client in Releases

- **Status**: Accepted
- **Date**: 2026-08-11

## Context

下載版使用者只需要把事證上傳到自己的 Google Drive，不應被要求建立 Google Cloud project、建立 OAuth client 或自行維護 `client_secrets.json`。目前的程式只會從 `data/config/client_secrets.json` 讀取 OAuth client 設定，因此第一次使用下載版會卡在開發者設定流程。

OAuth Desktop client 的 JSON 是應用程式識別設定，不是使用者授權結果；Installed App 的 client secret 不能視為真正的機密。相反地，OAuth refresh token 代表特定使用者的 Google 授權，必須留在該使用者的本機資料目錄。

## Decision

1. 正式 Google Cloud project 使用 External / Production，且只登記 `https://www.googleapis.com/auth/drive.file`。
2. release build 從未追蹤的 `build_secrets/google_oauth_client.json` 取得 OAuth Desktop client，並以 `google_oauth_client.json` 名稱嵌入 PyInstaller one-file EXE 的內部資源目錄。
3. frozen runtime 從 PyInstaller 的 `sys._MEIPASS` 讀取內嵌 client；原始碼執行可使用 `MAPLE_REPORTER_GOOGLE_OAUTH_CONFIG`，再 fallback 到 `build_secrets/` 與舊的 `data/config/client_secrets.json`。
4. `InstalledAppFlow.run_local_server(host="localhost", port=0)` 使用 loopback callback 與動態 port。OAuth client JSON 永不複製到 `data/config/`。
5. refresh token 只寫入使用者自己的 `%LOCALAPPDATA%/MapleClassicReporter/oauth_token.dpapi`，以 Windows DPAPI 保護；舊版 `data/config/token.json` 成功讀取後遷移並刪除，不列入 PyInstaller datas，也不放入發行 ZIP。DPAPI 可保護靜態檔案，但不能防禦同一 Windows 使用者權限下的惡意程式。
6. release build 若缺少或無法解析 `build_secrets/google_oauth_client.json` 必須失敗，不能產生無法登入的正式 EXE。

## Consequences

### Positive

- 下載版使用者可以直接按「連結 Google 帳號」，不需自行建立 Cloud project 或下載憑證。
- 每位使用者仍透過自己的 OAuth 授權連結自己的 Drive；開發者 token 不會被共用。
- `drive.file` 限制程式只操作由本程式建立或使用者透過本程式開啟的檔案，權限小於完整 `drive` scope。

### Trade-offs

- OAuth client JSON 必須由 release 維護者安全保存；它可以內嵌發布，但不可提交公開 Git repository。
- fork 專案者必須使用自己的 Google Cloud project 與 OAuth client。
- OAuth client 設定更新時需要重新建置並發布 EXE；使用者的 refresh token 不應被重新打包。
