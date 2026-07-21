# Blossom Academy LINE Bot — Hook 服務

本專案是一個基於 **FastAPI** 的 LINE Messaging API 伺服器，旨在協助學生進行英文作文的練習與評分。整合了 **Google Gemini API** 作為 AI 引擎，提供 OCR 辨識、語音轉寫、自動化作文評分及報告產生。

---

## 核心組件詳解

### 1. `main.py` (應用程式入口與路由分派)
`main.py` 是整個應用的入口點，核心功能為：
- **LINE Webhook 接收:** 定義 `/webhook/line` 端點，負責接收 LINE Platform 發送的 Webhook 事件。
- **安全性驗證:** 使用 `line_utils.py` 進行 HMAC-SHA256 簽章驗證，確保請求確實來自 LINE。
- **事件分派:** 解析 JSON 請求體，根據事件類型（`message`, `postback`）將請求非同步派發至 `handlers.py` 中對應的處理函數。
- **日誌設定:** 統一格式化 uvicorn 日誌（時間戳 + 層級 + 訊息），覆蓋 `uvicorn` / `uvicorn.error` / `uvicorn.access` 三個 logger。
- **靜態資源服務:** 提供 API 用於存取生成的評分報告 (`/webhook/scorepage`) 與網頁樣式 (`/webhook/style.css`)。

### 2. Python 模組架構說明

本專案將複雜邏輯拆分為以下模組：

| 模組名稱 | 功能說明 |
| :--- | :--- |
| **`main.py`** | **路由層**: HTTP 請求進入點，負責 Webhook 簽章驗證與請求分派。 |
| **`handlers.py`** | **業務邏輯層**: 處理不同類型的訊息事件（文字、圖片、音訊），串接各工具模組。 |
| **`gemini.py`** | **AI 服務層**: 封裝所有與 Google Gemini API 互動的邏輯（OCR、轉寫、評分、Markdown 轉 HTML）。 |
| **`english_essay.py`** | **檢測層**: 提供 `is_english_essay()` 函式，對文字內容進行格式檢測（字數、句數、開頭大寫比例）。 |
| **`config.py`** | **設定層**: 讀取 `settings.yaml`，集中管理所有全域參數、API 金鑰與提示詞模板。 |
| **`line_utils.py`** | **工具層**: 提供 LINE Messaging API 的認證配置 (`Configuration`) 及工具函式（簽章驗證）。 |

---

## 功能一覽

| 功能 | 說明 |
|------|------|
| **文字指令** | 回應 `grade` / `welcome` / `upload` / `menu` 等關鍵字，顯示對應的 Flex Message |
| **圖片 OCR + 評分** | 上傳圖片 → 辨識英文作文 → Gemini 評分 → 輸出 `.md` + `.html`（每日上限 10 次，處理中不接受重疊上傳） |
| **語音轉寫** | 上傳語音訊息 → 透過 Gemini API 轉寫為文字 |
| **英文作文檢測** | `is_english_essay()` 判斷 OCR 結果是否為英文作文，非英文作文不回傳評分 |
| **Markdown → HTML** | 評分結果自動轉換為卡片式 HTML，CSS 內嵌，支援手機 LIFF 顯示 |
| **LIFF 評分頁** | `GET /webhook/scorepage?id=<uuid>` 回傳對應的 HTML 評分報告 |
| **群組管理** | 僅管理員可使用 `@小英` 前綴觸發指令 |
| **Rich Menu** | 輸入 `menu` 即可連結特殊圖文選單 |
| **簽章驗證** | 所有 Webhook 請求皆經過 HMAC-SHA256 簽章驗證 |

---

## 專案結構

```
hook/
├── main.py                # FastAPI 應用入口（路由 + 啟動）
├── config.py              # 設定檔載入與常數
├── line_utils.py          # LINE 簽章驗證 + API 客戶端
├── handlers.py            # 各類訊息處理器 (text/image/audio/postback)
├── gemini.py              # Gemini API 呼叫封裝 (OCR / 轉寫 / 評分 / MD→HTML)
├── english_essay.py       # 英文作文檢測工具
├── style.css              # 卡片式 HTML 樣式（內嵌至輸出 HTML）
├── menu.sh                # 服務管理腳本（啟動/停止/查看 Log）
├── settings.yaml          # 設定檔（金鑰、Token、Flex 模板、提示詞）
├── requirements.txt       # Python 依賴
├── .gitignore
├── static/
│   └── scorepage.html     # LIFF 預設頁面（無 id 參數時顯示）
├── images/                # 接收的圖片暫存（gitignored）
├── audios/                # 接收的音訊暫存（gitignored）
├── output/                # 評分結果 .md/.html（gitignored）
├── archive/               # 舊版或未使用檔案（gitignored）
├── hook.log               # 服務日誌（gitignored）
└── .hook.pid              # 服務 PID 檔案（gitignored）
```

---

## 模組架構

```
main.py             路由層         HTTP 請求分派、簽章驗證
  ├── config.py ───── 設定層       settings.yaml 讀取、常數集中管理
  ├── line_utils.py ─ 工具層       LINE API 客戶端、HMAC 驗證
  ├── handlers.py ─── 業務層       文字/圖片/音訊/Postback 處理邏輯
  ├── gemini.py ───── AI 層        Gemini API 呼叫 (OCR / 轉寫 / 評分 / MD→HTML)
  └── english_essay.py            英文作文檢測（回傳清洗後文字）
```

- **config.py** — 一切設定的單一來源，其他模組從這裡讀取常數
- **line_utils.py** — 與 LINE Platform 的通訊基礎（簽章驗證、API Client）
- **gemini.py** — Gemini API 呼叫封裝：`ocr_image`、`transcribe_audio`、`score_essay`、`md_to_html`
- **handlers.py** — 各類事件的處理邏輯，依賴 config / line_utils / gemini
- **english_essay.py** — 判斷字數、句數、大寫比例，回傳 `(bool, reason, cleaned_text)`
- **main.py** — 最小化 glue code，只定義路由與事件分派

---

## 圖片處理流程

```
使用者上傳圖片
    → POST /webhook/line (type=image)           [main.py]
    → handle_image_message()                     [handlers.py]
    → 重疊上傳檢查（asyncio.Lock）               [handlers.py]
    → 每日用量檢查（每日 10 次上限）             [handlers.py]
    → 立即回覆「請稍候」Flex Message             [handlers.py]
    → 從 LINE 下載原始圖片，儲存至 images/
    → ocr_image(filepath)                        [gemini.py]
    → is_english_essay(text)                     [english_essay.py]
    → score_essay(cleaned, basename)             [gemini.py]  內部存 output/{id}.md
    → md_to_html(basename)                       [gemini.py]  內部存 output/{id}.html
    → push_message 回傳評分結果（不佔用 reply_token）
```

### 使用限制

| 限制 | 說明 |
|------|------|
| **每日 10 次** | 每位使用者每天最多上傳 10 張圖片進行 OCR 評分（以 Asia/Taipei 時區計算），達到上限後會收到「您今天已達每日使用上限，請明天再來。」的提示 |
| **不可重疊上傳** | 若使用者已有圖片正在處理中（OCR + 評分），系統不接受再次上傳，會回覆「您有圖片正在處理中，請稍候再上傳。」，需等待當前處理完成後才可繼續使用 |

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
llm_model: "gemini-3.1-flash-lite"
gemini_ocr_prompt: "將圖片中的英文作文識別出來..."
gemini_audio_prompt: "將語音內容轉寫為文字..."
elementary_prompt: "全民英檢初級寫作批改提示詞..."
MD_TO_HTML_PROMPT: "Markdown 轉 HTML 提示詞..."

admin: "LINE User ID 管理員"
admin_prefix: "@小英"
liff_uri: "https://liff.line.me/你的LIFF_ID"
endpoint_url: "https://你的域名/webhook/scorepage"

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
| `/webhook/scorepage` | `GET` | 回傳靜態評分頁（無 `?id=` 時）或對應的 HTML 評分報告 |
| `/webhook/style.css` | `GET` | 外部 CSS |

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

## 服務管理 (`menu.sh`)

| 選項 | 功能 |
|------|------|
| 1) 啟動服務 | 以 `nohup` 背景執行 uvicorn，記錄 PID |
| 2) 停止服務 | 依 PID 結束 uvicorn 程序（等待 5 秒，必要時強制終止） |
| 3) 重啟服務 | 依序執行停止 → 啟動 |
| 4) 查看 Log | 顯示 `hook.log` 最後 50 行 |
| 5) 即時 Log | `tail -f` 即時追蹤 log（Ctrl+C 退出） |
| 6) 清除 Log | 清空 `hook.log` 內容 |
| 7) 離開 | 退出選單 |

---

## 依賴

- `fastapi` — Web 框架
- `uvicorn` — ASGI 伺服器
- `line-bot-sdk` (v3) — LINE Messaging API SDK
- `aiohttp` — 非同步 HTTP 客戶端（呼叫 Gemini API）
- `PyYAML` — 設定檔解析
- `aenum`, `pydantic` 等 — SDK 相依套件

完整清單見 `requirements.txt`。
