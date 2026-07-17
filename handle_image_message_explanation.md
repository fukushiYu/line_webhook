# `handle_image_message` 流程解析

**檔案位置**: `handlers.py:66`

## 功能概述

接收使用者傳送的圖片 → OCR 擷取文字 → 判斷是否為英文作文 → 評分 → 回傳結果連結

---

## 流程逐步說明

### 1. 權限控制（L67-73）

```python
source = event.source
user_id = getattr(source, "user_id", "*")
group_id = getattr(source, "group_id", "*")
is_group = source.type == "group"
message_id = event.message.id
if is_group and user_id != ADMIN:
    return
```

- 從 `event` 取出使用者/群組資訊
- **如果是在群組中且不是 ADMIN，直接 return 不處理**（防止群組內其他人亂傳圖片觸發）
- 個人聊天（1對1）則不限制

### 2. 下載圖片（L74-82）

```python
async with AsyncApiClient(configuration) as api_client:
    blob_api = AsyncMessagingApiBlob(api_client)
    content = await blob_api.get_message_content(message_id)
    basename = f"{uuid.uuid4()}"
    filename = basename + ".jpg"
    os.makedirs("images", exist_ok=True)
    filepath = os.path.join("images", filename)
    with open(filepath, "wb") as f:
        f.write(content)
```

- 用 `AsyncMessagingApiBlob` 的 `get_message_content` 透過 **message_id** 下載原始圖片 binary
- 以 UUID 作為檔案名稱，存到 `images/` 資料夾
- **要點**：只要是 LINE 的圖片/影片/檔案，都是走 `AsyncMessagingApiBlob` 這個 API 來拿 content

### 3. OCR 擷取文字（L83）

```python
text = await ocr_image(filepath)
```

- 呼叫 `gemini.py` 的 `ocr_image`（送給 Gemini Vision API 做圖片文字辨識）
- 回傳辨識出的文字內容

### 4. 判斷是否為英文作文（L84-88）

```python
ok, reason, cleaned = is_english_essay(text)
if not ok:
    line_bot_api = AsyncMessagingApi(api_client)
    await line_bot_api.reply_message(...)
    return
```

- 呼叫 `english_essay.py` 的 `is_english_essay` 驗證：
  - 是否為英文
  - 是否達到一定字數／段落結構
- 如果不符合條件 → 回覆錯誤訊息給使用者（例如「這不是一篇英文作文：字數太少」）
- **通過才繼續往下**，這是 guard clause 模式

### 5. 評分 + 轉 HTML（L89-90）

```python
await score_essay(cleaned, basename)
await md_to_html(basename)
```

- `score_essay`：將清理後的文字送給 Gemini 評分，產生一個 Markdown 檔案（以 `basename` 命名）
- `md_to_html`：把 Markdown 轉成 HTML（可供網頁展示）
- 兩個函數都用 `basename`（UUID）當識別 key，確保檔案不衝突

### 6. 回覆 Flex Message 結果連結（L91-94）

```python
line_bot_api = AsyncMessagingApi(api_client)
flex_dict = FLEX_GRADE
flex_dict["body"]["contents"][1]["action"]["uri"] = f"{ENDPOINT_URL}?id={basename}"
await line_bot_api.reply_message(...)
```

- 從 config 載入預設的 Flex Message 模板（`FLEX_GRADE`）
- **動態修改**按鈕的 URI，加上 query parameter `?id={basename}`
- 使用者點擊後會開啟 `ENDPOINT_URL?id=<uuid>` 的網頁，顯示評分結果

---

## 給同事做類似功能的重點歸納

| 環節 | 關鍵程式碼 | 說明 |
|---|---|---|
| **下載媒體** | `AsyncMessagingApiBlob(api_client).get_message_content(message_id)` | LINE 所有使用者上傳的圖片/影片/音檔都走這條 |
| **暫存檔案** | `uuid.uuid4()` 命名 + `os.makedirs` + `open().write()` | 用 UUID 避免檔名衝突，記得建目錄 |
| **AI 處理** | `ocr_image` / `score_essay` / `transcribe_audio` | 抽象在 `gemini.py`，可抽換成其他模型 |
| **條件過濾** | `is_group and user_id != ADMIN: return` | 群組內只讓管理員觸發，個人不限制 |
| **回覆結果** | `FlexMessage` 動態改 URI / `TextMessage` | 用模板 + 動態參數產生回覆 |

---

## 做類似功能的快速上手

如果要**做類似但不同的功能**（例如使用者傳照片 → 辨識物品 → 回覆結果），只要：

1. 複製 `handle_image_message` 的整體架構
2. 把 `ocr_image` 換成你的辨識函數
3. 改回覆的訊息內容（`TextMessage` 或 `FlexMessage`）即可
