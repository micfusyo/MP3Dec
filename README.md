# MP3BatchConverter

一個以 Python 與 PyQt6 撰寫的 macOS GUI 批量音訊轉檔工具，適合把音樂檔轉成較低取樣率與位元率的 MP3，以配合特定播放裝置使用。

## 功能

- 以圖形介面選擇來源資料夾與目的資料夾
- 遞迴掃描子資料夾
- 支援輸入格式：`.mp3`、`.wav`、`.flac`、`.m4a`
- 輸出格式統一為 MP3
- 可選取樣率：`22050`、`32000`、`44100`、`48000`
- 可選位元率：`32k`、`64k`、`96k`、`128k`、`160k`、`192k`、`256k`、`320k`
- 轉換後檔名前自動加上 `CV_`
- 目的資料夾中自動重建原始子資料夾結構
- 同名輸出檔自動加流水號避免覆蓋
- 顯示進度條、目前檔案、成功/失敗統計
- 支援取消轉換
- 記住上次選取的資料夾與轉換選項
- 將錯誤與轉換紀錄寫入 log 檔

## 系統需求

- macOS
- Python 3.9 以上
- 已安裝 `ffmpeg`
- Python 套件：`PyQt6`

## 安裝與執行

1. 安裝 `ffmpeg`

```bash
brew install ffmpeg
```

2. 安裝 Python 套件

```bash
python3 -m pip install PyQt6
```

3. 啟動程式

```bash
python3 mp3_batch_converter.py
```

## 打包

### 建立 macOS `.app`

```bash
python3 -m pip install --user pyinstaller
env PYINSTALLER_CONFIG_DIR=.pyinstaller python3 -m PyInstaller -y --windowed --name MP3BatchConverter --clean mp3_batch_converter.py
```

輸出位置：

- `dist/MP3BatchConverter.app`

### 建立美化版 `.dmg`

```bash
python3 build_dmg.py
```

輸出位置：

- `dist/MP3BatchConverter.dmg`

## 設定與 Log

程式執行後會把設定與 log 存在使用者目錄：

- 設定檔：`~/Library/Application Support/MP3BatchConverter/config.json`
- Log：`~/Library/Logs/MP3BatchConverter/`

## 專案檔案

- `mp3_batch_converter.py`：主程式
- `build_dmg.py`：建立美化版 DMG 的腳本
- `README.md`：使用說明

## 注意事項

- 若 `ffmpeg` 不在系統路徑中，程式會顯示安裝方式提示
- 未經 Apple Developer 簽章的 `.app` 或 `.dmg` 在其他 Mac 上首次開啟時，可能會被 Gatekeeper 額外詢問
