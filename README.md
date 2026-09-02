# 行車雙鏡頭車牌辨識 + GPS 定位記錄系統

在車輛左右後照鏡各裝一支 USB 攝影機,行駛時即時偵測、辨識路邊車牌,並將辨識結果與當下的
GPS 經緯度一併寫入本地資料庫。

## 架構總覽

- **硬體**:樹莓派(或任何跑 Linux 的單板電腦/迷你電腦)+ 左右各一支 USB 攝影機 + 一支 USB GPS 接收器。
- **相機擷取** (`plate_scanner.camera`):兩支攝影機各自跑一條背景執行緒,只保留最新影格,避免其中一支延遲拖累另一支。
- **車牌偵測** (`plate_scanner.recognition.detector`):用 OpenCV Haar cascade 在畫面中快速框出疑似車牌區域,在樹莓派這類算力有限的裝置上仍可即時運作。內建 `resources/haarcascade_russian_plate_number.xml` 是 OpenCV 官方唯一內建的車牌類 cascade,並非針對特定國家車牌訓練,精準度有限,靠下面的混合辨識機制補強。
- **混合式辨識** (`plate_scanner.recognition.pipeline`):
  1. 本地用 Tesseract OCR 辨識裁切出的車牌區域。
  2. 信心值 ≥ `local_accept_confidence` → 直接採用本地結果,完全不連網。
  3. 信心值介於 `local_min_confidence` ~ `local_accept_confidence` 之間 → 視為不確定,若有啟用雲端 API(預設關閉),才將該小張裁切圖上傳做二次確認,取分數較高者。
  4. 信心值 < `local_min_confidence` → 直接捨棄。
- **GPS** (`plate_scanner.gps`):背景執行緒持續讀取定位,可用 `gpsd`(樹莓派建議做法)或直接讀 USB GPS 的 NMEA 字串,隨時提供「最新一筆定位」給辨識流程加註。
- **去重複** (`plate_scanner.dedup`):同一輛車經過鏡頭前會被拍到好幾張,加上 OCR 偶爾會有 1 個字元誤判,因此用「時間窗 + 編輯距離」判斷是否為同一次過車,避免同一台車存成好幾筆紀錄。
- **儲存** (`plate_scanner.storage`):純本地 SQLite,欄位包含車牌號碼、信心值、左右哪一側、經緯度、GPS 定位品質、是否經雲端覆核、裁切圖路徑、時間戳記。可另存車牌裁切小圖方便事後人工覆核。

## 安裝

```bash
sudo apt update
sudo apt install -y python3-pip tesseract-ocr gpsd gpsd-clients
git clone <this-repo> plate-scanner
cd plate-scanner
pip3 install -r requirements.txt
cp config.example.yaml config.yaml
```

> `requirements.txt` 中的 `gpsd-py3` 在部分新版 `setuptools` 環境下編譯會失敗(套件本身較舊),
> 若安裝失敗且你確定要用 `gps.backend: serial` 而非 `gpsd`,可以先把它從 `requirements.txt` 移除再安裝,
> `serial` 後端不依賴這個套件。

編輯 `config.yaml`:

- `cameras.left.source` / `cameras.right.source`:兩支攝影機對應的 `/dev/videoN`(用 `v4l2-ctl --list-devices` 確認)。
- `gps.backend`:樹莓派搭配 `gpsd` 服務通常最省事;若沒裝 `gpsd`,改成 `serial` 並填 `gps.serial_port`。
- `cloud.enabled`:預設 `false`(完全離線)。要開啟雲端覆核才需要填 `cloud.api_key`,並依實際採用的服務調整 `plate_scanner/recognition/cloud.py`(目前預設串接 Plate Recognizer 的 API 格式)。
- `storage.database_path` / `storage.crops_dir`:本地資料庫與車牌裁切圖存放位置。

## 執行

```bash
PYTHONPATH=src python3 -m plate_scanner.main --config config.yaml
```

開機自動啟動可參考 `systemd/plate-scanner.service`,依實際路徑與使用者調整後:

```bash
sudo cp systemd/plate-scanner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plate-scanner
```

## 查詢已記錄的車牌

資料庫是一般 SQLite 檔,可直接用 `sqlite3` 或任何 SQLite 工具查詢:

```bash
sqlite3 data/plate_scanner.sqlite3 "SELECT plate_text, latitude, longitude, datetime(captured_at,'unixepoch') FROM plate_sightings ORDER BY captured_at DESC LIMIT 20;"
```

## 測試

不需要接實體攝影機或 GPS 即可跑的單元測試(核心邏輯:設定檔載入、NMEA 解析、車牌文字正規化、
去重複判斷、SQLite 讀寫、混合辨識決策、相機執行緒使用假訊號源驗證):

```bash
python3 -m pytest
```

## 限制與注意事項

- 內建的 Haar cascade 車牌偵測器是通用款,對特定國家/樣式的車牌不一定準確,建議先在你實際會用的路況下測試 `local_accept_confidence` / `local_min_confidence` 門檻,必要時調整或換成專門訓練過的偵測模型。
- 這套系統會拍攝並記錄路上其他車輛的車牌與其出現的時間地點,屬於個人資料蒐集行為。上路使用前請確認符合當地法規(例如個資法、行車紀錄器相關規範),並僅用於合法目的(如行車糾紛蒐證、車隊管理等),避免用於跟蹤、騷擾或其他侵害他人隱私的用途。
- 目前資料完全存在本地裝置,沒有雲端備份;若要異地備份,可自行加上定期把 `data/` 目錄同步出去的排程。
