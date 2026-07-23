# 專案架構總覽

這是一個 **LINE Bot + Gemini AI** 的專案，讓使用者在 LINE 上傳圖片（英文作文手寫稿）→ 自動 OCR 辨識 → AI 評分 → 回傳結果網頁。

---

## 目錄

1. [檔案依賴層級圖](#1-檔案依賴層級圖)
2. [`main.py` ─ 應用程式入口 + Webhook 路由](#2-mainpy)
3. [`config.py` ─ 統一設定管理](#3-configpy)
4. [`line_utils.py` ─ LINE API 工具層](#4-line_utilspy)
5. [`handlers.py` ─ 事件處理器](#5-handlerspy)
6. [`english_essay.py` ─ 英文作文驗證邏輯](#6-english_essaypy)
7. [`gemini.py` ─ Gemini AI 呼叫層](#7-geminipy)
8. [完整資料流（Data Flow）](#8-完整資料流)

---

## 1. 檔案依賴層級圖

```
main.py                        ← FastAPI 伺服器，接收 LINE Webhook
  │
  ├── config.py                ← 讀取 settings.yaml + settings.local.yaml
  │     ├── settings.yaml      （公開設定：Flex 模板、提示詞）
  │     └── settings.local.yaml（機密設定：API Key、Token，已 .gitignore）
  │
  ├── line_utils.py            ← LINE SDK 簽章驗證 + API 客戶端工廠
  │
  └── handlers.py              ← 事件處理（文字/圖片/音訊/Postback）
        │
        ├── config.py          ← 取得 Flex 模板、管理員 ID 等
        ├── gemini.py          ← OCR / 評分 / 轉 HTML
        │     └── config.py
        └── english_essay.py   ← 驗證是否為英文作文
```

**依賴方向**：`main.py → handlers.py → gemini.py / english_essay.py`，`config.py` 與 `line_utils.py` 是底層基礎設施，被多個檔案共用。

---

## 2. `main.py`

**角色**：FastAPI 應用程式入口，對外暴露三個端點。

### 2.1 `POST /webhook/line/{channel_idx}` — LINE Webhook（支援多頻道）

```python
@app.post("/webhook/line/{channel_idx}")
async def webhook(channel_idx: int, request: Request, x_line_signature: str = Header(None)):
```

流程：

1. **頻道驗證**：`channel_idx` 對應 `settings.yaml` 中 `line` 陣列的索引，必須在範圍內
2. **簽章驗證**：從 Header 取出 `x-line-signature`，使用該頻道的 `channel_secret` 呼叫 `line_utils.verify_signature()` 確保請求來自 LINE
3. **解析事件**：將 request body 解析為 JSON，逐個處理 `events[]`
4. **依事件類型分派**：

| 事件類型 | 處理方式 | 說明 |
|---|---|---|
| `message.type == "image"` | `asyncio.create_task(handle_image_message(...))` | 圖片 → 非同步背景處理，不阻塞 Webhook 回應 |
| `message.type == "audio"` | `asyncio.create_task(handle_audio_message(...))` | 音訊 → 同上 |
| `message.type == "text"` | `await handle_message(...)` | 文字 → **同步等待**（因為回應需要 reply_token） |
| `type == "postback"` | `await handle_postback(...)` | Postback → 同步處理 |

> **Note**：圖片和音訊用 `create_task` 背景執行，因為下載 + AI 處理時間較長，不回 blocking 等待；文字訊息直接用 `await`，因為回應快。

### 2.2 `GET /webhook/scorepage` — 評分結果頁面

```python
@app.get("/webhook/scorepage")
async def score_page(id: str = Query(None)):
```

- 有 `id` 參數 → 回傳 `output/{id}.html`（AI 產生的評分結果網頁）
- 無 `id` 參數 → 回傳 `static/scorepage.html`（靜態頁面）

### 2.3 `GET /webhook/style.css`

```python
@app.get("/webhook/style.css")
async def serve_css():
```

- 提供 CSS 給評分結果頁面美化

---

## 3. `config.py`

**角色**：全域設定管理中心，啟動時一次性從 YAML 讀入所有設定，並以機密設定覆蓋。

```python
# 載入公開設定
with open("settings.yaml", "r", encoding="utf-8") as f:
    conf = yaml.safe_load(f)

# 以機密設定覆蓋
if os.path.exists("settings.local.yaml"):
    local_conf = yaml.safe_load(f)
    conf["gemini_api_key"] = local_conf["gemini_api_key"]
    for i, entry in enumerate(local_conf["line"]):
        conf["line"][i].update(entry)
```

### 3.1 `!include` 語法

支援在 YAML 中以 `!include path` 引用外部文字檔作為字串值，方便將大型提示詞抽離為獨立檔案：

```yaml
elementary_prompt: '!include prompt/elementary_prompt.txt'
```

透過 `_resolve()` 函數在載入時自動取代為檔案內容。

### 3.2 產出的設定常數

| 變數 | 用途 |
|---|---|
| `LINE_CONFIGS` | LINE 頻道設定陣列（每個元素包含 `channel_secret`, `channel_access_token`, `admin`, `admin_prefix`, `liff_uri`, `endpoint_url`, `rich_menu_id`） |
| `FLEX_WELCOME` / `FLEX_UPLOAD` / `FLEX_GRADE` / `FLEX_WAIT` | Flex Message 模板（dict） |
| `GEMINI_API_KEYS` | Gemini API Key 陣列（可多個輪流使用） |
| `LLM_MODEL` | Gemini 模型名稱 |
| `GEMINI_OCR_PROMPT` | OCR 用的 System Prompt |
| `GEMINI_AUDIO_PROMPT` | 語音辨識用的 System Prompt |
| `ELEMENTARY_PROMPT` | 評分作文用的 System Prompt（透過 `_resolve` 載入） |
| `MD_TO_HTML_PROMPT` | Markdown 轉 HTML 用的 System Prompt（透過 `_resolve` 載入） |

> **設計模式**：所有重要的字串和模板集中在 YAML，修改行為不需要改程式碼，改 YAML 就好。機密與公開設定分離，避免 Token 外洩。

---

## 4. `line_utils.py`

**角色**：LINE SDK 的共用工具函式，無全域實例，所有 function 皆由呼叫端傳入 `channel_config`。

### 4.1 `verify_signature(channel_secret, body, signature) -> bool`

- 使用 HMAC-SHA256 驗證 LINE 發送的 Webhook 請求是否合法
- 在 `main.py` 的 webhook 端點被呼叫

### 4.2 `get_line_api(channel_config) -> AsyncMessagingApi`

- Factory function，根據 `channel_config` 建立 `AsyncMessagingApi` 實例
- `handlers.py` 內部使用 `_make_api()` 達到相同效果

---

## 5. `handlers.py`

**角色**：所有 LINE 事件的商業邏輯處理器。所有 handler 皆接收 `channel_config: dict` 參數以支援多頻道。

### 5.1 `handle_message(event, channel_config)` — 文字訊息

| 使用者輸入 | 行為 |
|---|---|
| `grade` | 回傳評分專用的 Flex Message（按鈕 URI 設為該頻道的 `liff_uri`） |
| `welcome` | 回傳歡迎 Flex Message |
| `upload` | 回傳上傳 Flex Message |
| `menu` / `選單` | 將使用者的 Rich Menu 切換為指定選單 + 文字確認 |
| 其他 | Echo 使用者訊息 + 顯示 User ID / Group ID |

**管理員模式**：如果在群組中，只有 `user_id == admin` 且訊息以 `admin_prefix` 開頭時才會處理。

### 5.2 `handle_image_message(event, channel_config)` — 圖片訊息（核心功能）

完整流程已在另一份文件詳述，這裡只寫架構重點：

```
收到圖片事件
  │
  ├─ 權限檢查（群組只限 admin）
  │
  ├─ 重疊處理檢查（_processing_users + _state_lock）
  │     └─ 已有圖片在處理 → 回覆「請稍候再上傳」，結束
  │
  ├─ 每日用量檢查（_user_daily_usage + _usage_lock，每日 10 次）
  │     └─ 已達上限 → 回覆「已達每日使用上限」，結束
  │
  ├─ 立即回覆「請稍候」Flex Message（佔用 reply_token）
  │
  ├─ 下載圖片 binary（AsyncMessagingApiBlob.get_message_content）
  │
  ├─ 存檔至 images/{uuid}.jpg
  │
  ├─ OCR 辨識（gemini.ocr_image）
  │
  ├─ 驗證是否為英文作文（english_essay.is_english_essay）
  │     └─ 不合格 → 推播錯誤文字訊息（push_message），結束
  │
  ├─ AI 評分（gemini.score_essay）→ 產出 output/{uuid}.md
  │
  ├─ Markdown 轉 HTML（gemini.md_to_html）→ 產出 output/{uuid}.html
  │
  ├─ 推播 Flex Message（push_message），按鈕連結至 endpoint_url?id={uuid}
  │
  └─ finally: 從 _processing_users 中移除該 user_id
```

**關鍵細節**：
- 先用 `reply_message` 回覆「請稍候」，後續進度使用 `push_message`（因 reply_token 已用畢）
- `try/finally` 確保即使處理發生例外，`_processing_users` 也會被清除，不會卡死

### 5.3 `handle_audio_message(event, channel_config)` — 音訊訊息

類似圖片流程，但：
- 用 `get_message_content_with_http_info` 取得 raw data + Content-Type
- 根據 MIME type 決定副檔名（`AUDIO_EXT_MAP`）
- 存檔至 `audios/{uuid}.{ext}`
- 呼叫 `gemini.transcribe_audio` 進行語音轉文字
- 直接回傳文字內容給使用者（不評分）

### 5.4 `handle_postback(event, channel_config)` — Postback

目前為空實作（`pass`），留待未來擴充。

---

## 6. `english_essay.py`

**角色**：純函數工具，驗證一段文字是否符合「英文作文」的基本格式。

```python
def is_english_essay(text: str) -> tuple[bool, str, str]:
```

**回傳值**：`(ok: bool, reason: str, cleaned: str)`

**檢查項目**：

| 檢查 | 條件 | 失敗訊息 |
|---|---|---|
| 是否空白 | `text.strip()` 為空 | "文字內容為空白，無法判斷" |
| 字數 | `len(words) < 30` | "字數不足（目前 N 詞，需至少 30 詞）" |
| 句子數 | `len(sentences) < 2` | "句子數量不足（目前 N 句，需至少 2 句）" |
| 大寫開頭比例 | 大寫開頭句子 < 50% | "大部分句子未以大寫開頭，不似英文作文格式" |

> **設計原則**：先做輕量級的規則過濾，阻擋明顯不是作文的輸入，避免浪費 Gemini API 的費用與時間。

---

## 7. `gemini.py`

**角色**：所有 Gemini API 呼叫的封裝層。對外提供 4 個公開函數。

### 7.1 底層函數

#### `_call_gemini(filepath, mime_type, prompt) -> str`

- 讀取檔案 → base64 編碼 → 與 prompt 一起組成 Gemini API 的 payload
- 隨機選取一組 API key（來自 `GEMINI_API_KEYS` 陣列）達到輪流使用
- 用 `aiohttp` 非同步呼叫 Gemini `generateContent` 端點

#### `_call_gemini_text(prompt, text, file_id) -> str`

- 純文字版的 Gemini 呼叫（不帶檔案）
- 將回傳結果寫入 `output/{file_id}.md`

### 7.2 公開函數

| 函數 | 內部使用 | 用途 |
|---|---|---|
| `ocr_image(filepath)` | `_call_gemini(..., "image/jpeg", GEMINI_OCR_PROMPT)` | 圖片 → 文字 |
| `transcribe_audio(filepath, mime_type)` | `_call_gemini(..., mime_type, GEMINI_AUDIO_PROMPT)` | 音訊 → 文字 |
| `score_essay(text, file_id)` | `_call_gemini_text(ELEMENTARY_PROMPT, text, file_id)` | 作文評分 → 寫入 `.md` |
| `md_to_html(file_id)` | 直接呼叫 Gemini + `_extract_html()` | `.md` → `.html` |

#### `_extract_html(raw)` 的特殊處理

- Gemini 回傳的 HTML 可能包含 Markdown code block（```` ```html...``` ````）
- 此函數會從 `<!DOCTYPE` / `<html` 開始擷取，並移除結尾的 ` ``` `

---

## 8. 完整資料流

以下以「使用者在 LINE 上傳英文作文照片」為例：

```
使用者
  │
  │ 傳送圖片
  ▼
LINE Platform
  │
  │ POST /webhook/line/{channel_idx} (x-line-signature)
  ▼
main.py:webhook()
  │
  ├─ 驗證 channel_idx 範圍
  ├─ line_utils.verify_signature()  ─── 使用該頻道的 channel_secret 驗證簽章
  │
  ├─ 判斷 type=message, message.type=image
  │
  └─ asyncio.create_task(handle_image_message(event, channel_config))
        │
        ▼
      handlers.py:handle_image_message()
        │
        ├─ 權限檢查（群組 + admin）
        │
        ├─ 重疊處理檢查（_processing_users）
        │     └─ 忙碌中 → 回覆「請稍候」→ 結束
        │
        ├─ 每日用量檢查（10 次/日）
        │     └─ 已達上限 → 回覆「請明天再來」→ 結束
        │
        ├─ 回覆「請稍候」Flex Message（佔用 reply_token）
        │
        ├─ AsyncMessagingApiBlob.get_message_content(message_id)
        │     │
        │     └─ LINE Platform ─── 下載原始圖片
        │
        ├─ 存檔 images/{uuid}.jpg
        │
        ├─ gemini.ocr_image(filepath)
        │     │
        │     └─ _call_gemini(filepath, "image/jpeg", GEMINI_OCR_PROMPT)
        │           │
        │           └─ Gemini API ─── 圖片辨識回傳文字
        │
        ├─ english_essay.is_english_essay(text)
        │     │
        │     ├─ 不合格 → LINE push_message 錯誤訊息 ─── 結束
        │     │
        │     └─ 合格 → 繼續
        │
        ├─ gemini.score_essay(cleaned, basename)
        │     │
        │     └─ _call_gemini_text(ELEMENTARY_PROMPT, text, basename)
        │           │
        │           ├─ Gemini API ─── 評分回傳 Markdown
        │           │
        │           └─ 寫入 output/{basename}.md
        │
        ├─ gemini.md_to_html(basename)
        │     │
        │     ├─ 讀取 output/{basename}.md
        │     ├─ Gemini API ─── Markdown → HTML
        │     └─ 寫入 output/{basename}.html
        │
        ├─ LINE push_message Flex Message（附評分結果連結）
        │     │
        │     └─ 按鈕連結 → GET /webhook/scorepage?id={basename}
        │                     │
        │                     └─ FastAPI 回傳 output/{basename}.html
        │                          │
        │                          ▼
        │                     使用者瀏覽器看到評分結果
        │
        └─ finally: 從 _processing_users 清除 user_id
```

---

## 快速參考：如果要加新功能

| 你想做什麼 | 要改的檔案 | 參考現有函數 |
|---|---|---|
| 處理新的訊息類型（如影片） | `main.py` + `handlers.py` | `handle_image_message` / `handle_audio_message` |
| 加新的文字指令 | `handlers.py` 的 `handle_message` | `if lower_text == "xxx"` |
| 用 Gemini 做不同的事 | `gemini.py` | `ocr_image` / `score_essay` 模式 |
| 改評分規則 | `english_essay.py` | `is_english_essay` |
| 新增設定值 | `config.py` + `settings.yaml` | 現有變數模式 |
| 加新的 HTTP 路由 | `main.py` | `@app.get/post` |
| 新增 LINE 頻道 | `settings.yaml` + `settings.local.yaml` | 擴充 `line` 陣列即可 |
