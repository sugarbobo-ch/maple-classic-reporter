# Maple Classic Reporter 更新流程

## 使用者體驗

程式啟動完成後會在背景檢查 GitHub Releases。`auto_update_enabled` 預設為 `true`，新版會自動下載與驗證，但不會在使用者操作中強制關閉程式。

Header 右側、明暗模式按鈕左側會依狀態顯示：

- 「有可用更新」：自動下載關閉時的手動入口。
- 圓形進度：背景下載中的百分比。
- 「重啟應用」：更新已準備完成，按下後會關閉、套用並自動重開。
- 「完成後重啟」：目前仍在錄影、影片處理或送出回報。

使用者資料仍保存於 `%LOCALAPPDATA%\MapleClassicReporter\`，不會被更新包覆蓋。

## 發佈者設定

GitHub Actions 的 release workflow 會建置主程式與隨附的 `MapleClassicReporterUpdater.exe`，並產生完整 ZIP、bundle manifest、update manifest 及上一個相容版本的檔案級差分包。

簽章設定如下：

- `UPDATE_SIGNING_KEY`：GitHub Actions Secret，Ed25519 private key 的 base64 編碼。只存於 GitHub，不提交到 repository。
- public key：嵌入 frozen 客戶端，用來驗證 update manifest。`MAPLE_REPORTER_UPDATE_PUBLIC_KEY` 只作為測試或金鑰輪替的環境覆寫，不是正式 private key 儲存位置。

第一個包含 updater 的版本仍是導入版本；既有舊版使用者需最後一次手動下載完整 ZIP。之後的版本由主程式直接使用 GitHub Releases 更新。

## 更新檔暫存與清理

下載與交易檔案放在 `%LOCALAPPDATA%\MapleClassicReporter\updates\`。成功重開並完成健康確認後，程式會刪除 `.part`、更新包、交易暫存、rollback 備份、pending state 與 updater 暫存副本，只保留小型狀態快取及受限的更新紀錄。
