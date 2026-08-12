# 下一個 Agent：重構與建置交接

## 目標

在保留目前 UI 與使用流程的前提下，完成下列重構、測試及 Windows 執行檔建置。

明確排除：不要實作「證據保留 7 天」或任何自動保存期限功能。

## 工作規則

- 先閱讀專案 `AGENTS.md` 與 `C:\Users\lls03\.codex\RTK.md`。
- 保留目前 dirty worktree，不得 reset、checkout、覆蓋或刪除使用者既有修改。
- 不得 commit、tag、push、建立 GitHub Release 或公開上傳檔案。
- 不得硬編碼音訊裝置、使用者路徑、OAuth 憑證、API key 或 Discord webhook。
- 使用 `apply_patch` 修改原始碼。
- 完成後只清理本次建置產生、且可安全重建的舊建置輸出；不得清除原始碼。

## 實作順序

### 1. 防止誤判表單送出成功

- 修改 `src/maple_reporter/automation/form_filler.py`。
- 點擊送出後必須等待並驗證明確的成功提示、成功頁面或可靠 URL 狀態，不能只等待固定秒數就回傳成功。
- timeout、驗證訊息、網站錯誤或頁面結構不符均回傳失敗及可理解的中文原因。
- `src/maple_reporter/gui/main_window.py` 只能在上傳成功且表單確認成功後執行既有的「立即自動刪除」選項。
- 不新增 7 天保留機制。

### 2. 拆分 MainWindow 職責

- 將 Replay、Submission、Settings、History 邏輯拆成小型 controller/service/model。
- `MainWindow` 保留畫面組裝與訊號連接，不承擔錄影、上傳、歷史儲存的細節。
- 採漸進式重構，避免一次大改 UI 或改變既有按鈕位置、文字與操作行為。

### 3. 統一音訊擷取與混流

- 合併一般錄影與回放緩衝重複的 WASAPI loopback、音訊裝置列舉、選擇及 mux 邏輯。
- 裝置清單必須來自使用者電腦，不得硬編碼裝置名稱。
- 支援藍牙耳機、預設輸出裝置及裝置剛連線時的短暫無資料狀態，不能因開頭靜音就永久誤判沒有聲音。
- 裝置中途失效時回報清楚的中文錯誤，並完整釋放 thread、buffer、PyAV container 與音訊 handle。

### 4. OCR 模組化

- 將 `src/maple_reporter/ocr/win_ocr.py` 拆分為影像裁切／正規化、OCR provider、候選排序／地圖名稱比對。
- 保持現有辨識輸出相容，為複雜候選排序補上固定圖片或 mock 測試。

### 5. 錄影狀態機

- 使用明確狀態：`IDLE`、`WARMING`、`READY`、`SAVING`、`STOPPING`、`ERROR`。
- UI 按鈕是否可按必須由狀態決定。
- 維持目前同時間只能儲存一個回放分段的限制；儲存完成後可再次按下，不停止持續緩衝。

### 6. 儲存與診斷改善

- `history.json` 改用暫存檔、flush/fsync、atomic replace，避免程式中斷造成檔案半寫入。
- 將重要的 `except Exception: pass` 改成結構化 logging；log 不得包含 token、API key、webhook 完整網址或 OAuth authorization code。
- 將棄用的 `mss.mss()` 更新為目前支援的 API，確認相依版本相容。

### 7. 發布流程安全修正

- 修正 `scripts/release.py` 只 stage 部分原始碼及強制覆寫 tag 的問題，但不要實際執行發布。
- release 應拒絕 dirty worktree、禁止 force-push tag，並確保建置來源是明確 commit/tag。
- `.github/workflows/release.yml` 使用 `uv sync --frozen`，縮小 job 權限，並為未提交的 OAuth build resource 提供 GitHub Secret 注入方案。
- 不得把真實 OAuth JSON、client secret 或其他憑證提交到 Git。

## 必要驗證

- 執行全部 unit tests。
- 新增表單成功確認、失敗／timeout、不誤刪證據測試。
- 驗證輸出 MP4 同時具有影像軌與 AAC 音訊軌。
- 驗證藍牙／預設裝置解析不依賴硬編碼名稱。
- 驗證回放緩衝重複開始、停止、儲存後不殘留 thread，frame/audio buffer 維持上限。
- 執行至少兩小時模擬壓力測試或等效的加速時間測試。
- 執行 `pip-audit`、Bandit、`git diff --check`。

## 建置輸出

- 使用 `scripts/build_windows.ps1` 與專案既有 PyInstaller spec 建置。
- 正式建置所需 OAuth resource 必須從本機 `build_secrets` 取得，確認它受 `.gitignore` 保護。
- 不得發布或上傳產物。
- 回報：
  - 所有修改檔案。
  - 測試與壓力測試結果。
  - EXE 絕對路徑、檔案大小與 SHA-256。
  - EXE 是否有音訊軌相關 runtime 依賴缺漏。
  - 尚未解決的風險與手動驗證步驟。
