# ADR 0003: Google Drive Integration for Evidence Upload

- **Status**: Accepted
- **Date**: 2026-08-01

## Context

遊戲橘子外掛回報表單需要提供 `https://` 的圖片或影片事證網址。為了確保隱私、安全性與長久穩定性，使用者需要能夠綁定自己的 **Google Drive** 來自動上傳事證。

## Decision

1. 使用 **Google Drive API (OAuth2 PKCE Flow)** 支援使用者一鍵綁定登入個人的 Google 帳號。
2. 應用程式會在使用者雲端硬碟建立專屬資料夾（例如 `MapleClassic_Reports/`）。
3. 擷取畫面或選擇影片後，程式自動將媒體檔案上傳至該資料夾，並設定權限為「知道連結者皆可查看」（Anyone with link can view），並取得公開分享連結 (`https://drive.google.com/file/d/.../view?usp=sharing`)。
4. 使用者可在 Google Drive 與 Discord 間擇一上傳；Google Drive 為官方審查的建議選項。
5. 上傳成功後，程式將產生的事證連結自動填入回報表單第 5 欄。

## Consequences

- **優點**:
  - 不需要維護第三方圖床，圖片與影片安全儲存於玩家自己的 Google Drive 中。
  - Google Drive 支援圖片與大容量影片（MP4/MKV 等）。
  - Discord 可用於 10 MiB 內的短片快速分享。
- **缺點**:
  - 使用者初次需執行 Google 帳號 OAuth 授權綁定。
  - Discord 連結不適合作為唯一的長期事證保存位置。
