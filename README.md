# Blossom Academy LINE Bot — Hook 服務

基於 **FastAPI** 的 LINE Messaging API 伺服器，提供圖片 OCR、語音轉寫、Flex 選單等功能，搭配 Google Gemini API 作為 AI 引擎。

---

## 功能一覽

| 功能 | 說明 |
|------|------|
| **文字指令** | 回應 `grade` / `welcome` / `upload` / `menu` 等關鍵字，顯示對應的 Flex Message |
| **圖片 OCR** | 上傳圖片 → 透過 Gemini API 辨識圖片中的英文作文文字 |
| **語音轉寫** | 上傳語音訊息 → 透過 Gemini API 轉寫為文字 |
| **群組管理** | 僅管理員可使用 `@小英` 前綴觸發指令 |
| **Rich Menu** | 輸入 `menu` 即可連結特殊圖文選單 |
| **LIFF 評分頁** | `GET /webhook/scorepage` 回傳靜態評分頁面 |
| **簽章驗證** | 所有 Webhook 請求皆經過 HMAC-SHA256 簽章驗證 |
| **英文作文檢測** | `english_essay.py` 提供 `is_english_essay()` 判斷是否為英文作文 |

---

## 專案結構

```
hook/
├── main.py                # FastAPI 應用入口（路由 + 啟動）
├── config.py              # 設定檔載入與常數
├── line_utils.py          # LINE 簽章驗證 + API 客戶端
├── handlers.py            # 各類訊息處理器 (text/image/audio/postback)
├── gemini.py              # Gemini API 呼叫封裝 (OCR / 轉寫)
├── english_essay.py       # 英文作文檢測工具
├── menu.sh                # 服務管理腳本（啟動/停止/查看 Log）
├── settings.yaml          # 設定檔（金鑰、Token、Flex 模板）
├── requirements.txt       # Python 依賴
├── .gitignore
├── static/
│   └── scorepage.html     # LIFF 評分頁面
├── images/                # 接收的圖片暫存
├── audios/                # 接收的音訊暫存
├── hook.log               # 服務日誌
└── .hook.pid              # 服務 PID 檔案
```

---

## 模組架構

```
main.py             路由層         HTTP 請求分派、簽章驗證
  ├── config.py ───── 設定層       settings.yaml 讀取、常數集中管理
  ├── line_utils.py ─ 工具層       LINE API 客戶端、HMAC 驗證
  ├── handlers.py ─── 業務層       文字/圖片/音訊/Postback 處理邏輯
  └── gemini.py ───── AI 層        Google Gemini API 呼叫 (OCR / 轉寫)
```

- **config.py** — 一切設定的單一來源，其他模組從這裡讀取常數
- **line_utils.py** — 與 LINE Platform 的通訊基礎（簽章驗證、API Client）
- **gemini.py** — 對 Gemini API 的唯二呼叫（`ocr_image` / `transcribe_audio`），隱藏 API 細節
- **handlers.py** — 各類事件的處理邏輯，依賴 config / line_utils / gemini
- **main.py** — 最小化 glue code，只定義路由與事件分派

---

## 安裝與執行

### 1. 建立虛擬環境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 設定 `settings.yaml`

```yaml
channel_secret: "你的 LINE Channel Secret"
channel_access_token: "你的 LINE Channel Access Token"

gemini_api_key:
  - "你的 Gemini API Key (可多組輪換)"
llm_model: "gemini-2.0-flash-exp"
gemini_prompt: "將圖片中的英文作文識別出來，不要做任何的修改"
gemini_audio_prompt: "將語音內容轉寫為文字，不要做任何的修改"

admin: "LINE User ID 管理員"
admin_prefix: "@小英"
liff_uri: "https://liff.line.me/你的LIFF_ID"

flex_welcome:   # Flex Message JSON (bubble)
flex_upload:    # Flex Message JSON (bubble)
flex_grade:     # Flex Message JSON (bubble)
```

### 4. 啟動服務

**使用 menu.sh 選單：**
```bash
bash menu.sh
# 選擇 1) 啟動服務
```

**直接啟動：**
```bash
uvicorn main:app --port 9000
```

---

## Webhook 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/webhook/line` | `POST` | LINE Messaging API Webhook（需附 `X-Line-Signature`） |
| `/webhook/scorepage` | `GET` | 回傳 LIFF 評分靜態頁面 |

---

## 文字指令對照

| 指令 | 適用場合 | 行為 |
|------|----------|------|
| `grade` | 私訊 / 群組 | 傳送評分 Flex Message，按鈕導向 LIFF 評分頁 |
| `welcome` | 私訊 / 群組 | 傳送歡迎 Flex Message |
| `upload` | 私訊 / 群組 | 傳送上傳提示 Flex Message |
| `menu` / `選單` | 私訊 / 群組 | 連結 Rich Menu 至該使用者 |
| 其他文字 | 私訊 | Echo 回覆使用者 ID 與群組 ID |
| `@小英 <指令>` | 群組（限管理員） | 管理員專用前綴 |

---

## 圖片 OCR 流程

```
使用者上傳圖片
    → POST /webhook/line (type=image)          [main.py]
    → handle_image_message()                     [handlers.py]
    → 從 LINE 下載原始圖片，儲存至 images/
    → ocr_image(filepath)                        [gemini.py]
    → 回傳辨識文字至 LINE
```

## 語音轉寫流程

```
使用者傳送語音訊息
    → POST /webhook/line (type=audio)           [main.py]
    → handle_audio_message()                     [handlers.py]
    → 從 LINE 下載音訊，依 Content-Type 決定副檔名
    → transcribe_audio(filepath, mime)           [gemini.py]
    → 回傳轉寫文字至 LINE
```

---

## 簽章驗證

所有來自 LINE 的 Webhook 請求都會經過 `line_utils.verify_signature()` 驗證（HMAC-SHA256），驗證失敗回傳 `400 Invalid signature`。

---

## 英文作文檢測 (`english_essay.py`)

```python
from english_essay import is_english_essay

is_english_essay(text)  # → True / False
```

判斷規則：

1. 排除包含中日韓泰文字的內容
2. 只允許英文字母、標點、數字、空白
3. 字數至少 30 詞
4. 至少 2 句以上
5. 超過 50% 的句子開頭為大寫

---

## 服務管理 (`menu.sh`)

| 選項 | 功能 |
|------|------|
| 1) 啟動服務 | 以 `nohup` 背景執行 uvicorn，記錄 PID |
| 2) 停止服務 | 依 PID 結束 uvicorn 程序 |
| 3) 查看 Log | 顯示 `hook.log` 最後 50 行 |
| 4) 離開 | 退出選單 |

---

## 依賴

- `fastapi` — Web 框架
- `uvicorn` — ASGI 伺服器
- `line-bot-sdk` (v3) — LINE Messaging API SDK
- `aiohttp` — 非同步 HTTP 客戶端（呼叫 Gemini API）
- `PyYAML` — 設定檔解析
- `aenum`, `pydantic` 等 — SDK 相依套件

完整清單見 `requirements.txt`。
