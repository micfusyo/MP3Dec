# Changelog

## 1.0.1 - 2026-04-25

- 修正從 `.app` 或 `.dmg` 安裝後啟動時，因 Finder 環境變數 `PATH` 不完整而找不到 Homebrew `ffmpeg` 的問題
- 新增對 macOS 常見 `ffmpeg` 安裝位置的主動搜尋，包括 `/opt/homebrew/bin/ffmpeg` 與 `/usr/local/bin/ffmpeg`
- 新增 `FFMPEG_PATH` 環境變數支援，可手動指定 `ffmpeg` 執行檔路徑

## 1.0.0 - 2026-04-24

- 初次釋出 MP3BatchConverter
- 以 PyQt6 提供 macOS GUI 批量音訊轉檔介面
- 支援 `.mp3`、`.wav`、`.flac`、`.m4a` 轉成 MP3
- 支援自訂取樣率與位元率
- 支援遞迴掃描來源資料夾並重建目的資料夾結構
- 自動為輸出檔名加上 `CV_` 前綴，並在同名時自動改名
- 提供轉換進度、錯誤顯示、取消功能與 log 紀錄
- 提供 macOS `.app` 與美化版 `.dmg` 打包流程
