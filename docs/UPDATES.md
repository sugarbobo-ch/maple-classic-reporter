# Maple Classic Reporter 更新流程

## 使用者體驗

程式啟動完成後會在背景檢查 GitHub Releases。`auto_update_enabled` 預設為 `true`，新版會自動下載與驗證，但不會在使用者操作中強制關閉程式。

Header 右側、明暗模式按鈕左側會依狀態顯示：

- 「有可用更新」：自動下載關閉時的手動入口。
- 圓形進度：背景下載中的百分比。
- 「重啟應用」：更新已準備完成，按下後會關閉、套用並自動重開。
- 「完成後重啟」：目前仍在錄影、影片處理或送出回報。

「關於」頁面的「應用程式更新」區塊提供完整控制與資訊：

- 開關自動下載，並選擇穩定版或預覽版頻道。
- 手動檢查、立即下載、取消下載與重啟套用。
- 顯示完整包／差分包、已下載與總大小，以及所需與可用磁碟空間。
- 以預設收合的區塊顯示目標版本更新內容。Release notes 支援 GitHub Flavored Markdown，會先清理不安全 HTML、不載入遠端圖片；外部連結由系統瀏覽器開啟，也可直接前往 GitHub Release。

按下「重啟應用」後，獨立 updater 會在背景執行解壓、檔案替換、驗證與重新啟動，主執行緒以 60 FPS 更新平滑進度視窗。Windows 環境優先使用系統 `tar.exe` 解壓並依已寫入的檔案大小回報實際進度；無法使用時才退回 Python 解壓流程。

使用者資料仍保存於 `%LOCALAPPDATA%\MapleClassicReporter\`，不會被更新包覆蓋。

## 下載、驗證與套用順序

1. 從 GitHub Release 取得並驗證簽章過的 update manifest。
2. 目前版本有相容差分包時優先選用差分包，否則下載完整 ZIP；下載前先確認磁碟空間。
3. 下載到 `.part` 暫存檔並即時回報位元組與百分比，完成後驗證檔案大小與 SHA-256。
4. 程式閒置後啟動隨附的 `MapleClassicReporterUpdater.exe`。updater 建立交易與 rollback 資料，套用差分或完整包，再啟動更新後的應用程式進行健康確認。
5. 套用或健康確認失敗時保留診斷資料並嘗試還原；成功後由新版本清理交易檔案。

## 發佈者設定

GitHub Actions 的 release workflow 會建置主程式與隨附的 `MapleClassicReporterUpdater.exe`，並產生完整 ZIP、bundle manifest、update manifest 及上一個相容版本的檔案級差分包。

簽章設定如下：

- `UPDATE_SIGNING_KEY`：GitHub Actions Secret，Ed25519 private key 的 base64 編碼。只存於 GitHub，不提交到 repository。
- public key：嵌入 frozen 客戶端，用來驗證 update manifest。`MAPLE_REPORTER_UPDATE_PUBLIC_KEY` 只作為測試或金鑰輪替的環境覆寫，不是正式 private key 儲存位置。

第一個包含 updater 的版本仍是導入版本；既有舊版使用者需最後一次手動下載完整 ZIP。之後的版本由主程式直接使用 GitHub Releases 更新。GitHub Release 的說明文字會傳到客戶端「關於」頁面，因此請使用清楚的 Markdown 標題與條列，並將完整 release notes 維護於 `docs/releases/<version>.md`。

## 更新檔暫存與清理

下載與交易檔案放在 `%LOCALAPPDATA%\MapleClassicReporter\updates\`。成功重開並完成健康確認後，程式會刪除 `.part`、更新包、交易暫存、rollback 備份、pending state 與 updater 暫存副本，只保留小型狀態快取及受限的更新紀錄。
