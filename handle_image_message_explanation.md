# `handle_image_message` 流程解析

**檔案位置**: `handlers.py:86`

## 功能概述

接收使用者傳送的圖片 → OCR 擷取文字 → 判斷是否為英文作文 → 評分 → 回傳結果連結

---

## 流程逐步說明

### 1. 權限控制（L94-96）

```python
source = event.source
user_id = getattr(source, "user_id", "*")
group_id = getattr(source, "group_id", "*")
is_group = source.type == "group"
message_id = event.message.id
if is_group and user_id != channel_config["admin"]:
    return
```

- 從 `event` 取出使用者/群組資訊
- **如果是在群組中且不是 `admin`，直接 return 不處理**（防止群組內其他人亂傳圖片觸發）
- 個人聊天（1對1）則不限制

### 2. 重疊處理檢查（L98-114）

```python
async with _state_lock:
    if user_id in _processing_users:
        busy = True
    else:
        busy = False
        _processing_users.add(user_id)

if busy:
    line_bot_api = _make_api(channel_config)
    await line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="您有圖片正在處理中，請稍候再上傳。")],
        )
    )
    return
```

- `_processing_users` 集合記錄「正在處理圖片的 user_id」
- 若該使用者的上一張圖片還在處理中，直接回覆錯誤並中斷
- **目的**：避免使用者短時間內大量上傳，造成 Gemini API 浪費或伺服器負載

### 3. 每日用量檢查（L117-133）

```python
async with _usage_lock:
    today = datetime.now(TAIPEI_TZ).date()
    record = _user_daily_usage.get(user_id)
    if record and record["date"] == today:
        if record["count"] >= DAILY_IMAGE_LIMIT:  # 10 次
            return  # 回覆「已達每日使用上限」
        record["count"] += 1
    else:
        _user_daily_usage[user_id] = {"date": today, "count": 1}
```

- `_user_daily_usage` 以 `user_id` 為 key，紀錄「當日日期 + 已使用次數」
- 每日上限固定 **10 次**（以 `Asia/Taipei` 時區計算）
- 達到上限後會收到「您今天已達每日使用上限，請明天再來。」

### 4. 回覆「請稍候」+ 下載圖片（L135-152）

```python
api_client = AsyncApiClient(Configuration(access_token=channel_config["channel_access_token"]))
line_bot_api = AsyncMessagingApi(api_client)
await line_bot_api.reply_message(
    ReplyMessageRequest(
        reply_token=event.reply_token,
        messages=[FlexMessage(alt_text="請稍候", contents=FlexContainer.from_dict(FLEX_WAIT))],
    )
)
blob_api = AsyncMessagingApiBlob(api_client)
content = await blob_api.get_message_content(message_id)
basename = f"{uuid.uuid4()}"
filename = basename + ".jpg"
os.makedirs("images", exist_ok=True)
filepath = os.path.join("images", filename)
with open(filepath, "wb") as f:
    f.write(content)
await api_client.close()
```

- **先立即回覆「請稍候」Flex Message**，佔用 `reply_token`
- 用 `AsyncMessagingApiBlob` 的 `get_message_content` 透過 **message_id** 下載原始圖片 binary
- 以 UUID 作為檔案名稱，存到 `images/` 資料夾
- **要點**：之後的進度訊息都只能使用 `push_message`（因為 reply_token 已用畢）

### 5. OCR 擷取文字（L154）

```python
text = await ocr_image(filepath)
```

- 呼叫 `gemini.py` 的 `ocr_image`（送給 Gemini Vision API 做圖片文字辨識）
- 回傳辨識出的文字內容

### 6. 判斷是否為英文作文（L155-164）

```python
ok, reason, cleaned = is_english_essay(text)
if not ok:
    line_bot_api = _make_api(channel_config)
    await line_bot_api.push_message(
        PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=f"這不是一篇英文作文：{reason}")],
        )
    )
    return
```

- 呼叫 `english_essay.py` 的 `is_english_essay` 驗證：
  - 是否為英文
  - 是否達到一定字數（30 詞）／句子數（2 句）／大寫開頭比例（50%）
- 如果不符合條件 → `push_message` 推播錯誤訊息給使用者
- **注意**：這裡使用 `push_message` 而非 `reply_message`，因為 `reply_token` 已經在步驟 4 用掉了

### 7. 評分 + 轉 HTML（L166-167）

```python
await score_essay(cleaned, basename)
await md_to_html(basename)
```

- `score_essay`：將清理後的文字送給 Gemini 評分，產生一個 Markdown 檔案（以 `basename` 命名）
- `md_to_html`：把 Markdown 轉成 HTML（可供網頁展示）
- 兩個函數都用 `basename`（UUID）當識別 key，確保檔案不衝突

### 8. 推播 Flex Message 結果連結（L168-176）

```python
flex_dict = FLEX_GRADE
flex_dict["body"]["contents"][1]["action"]["uri"] = f"{channel_config['endpoint_url']}?id={basename}"
line_bot_api = _make_api(channel_config)
await line_bot_api.push_message(
    PushMessageRequest(
        to=user_id,
        messages=[FlexMessage(alt_text="評分結果", contents=FlexContainer.from_dict(flex_dict))],
    )
)
```

- 從 config 載入預設的 Flex Message 模板（`FLEX_GRADE`）
- **動態修改**按鈕的 URI，加上 query parameter `?id={basename}`
- 使用者點擊後會開啟 `endpoint_url?id=<uuid>` 的網頁，顯示評分結果

### 9. 清理（L177-179）

```python
finally:
    async with _state_lock:
        _processing_users.discard(user_id)
```

- `try/finally` 確保無論處理成功或失敗，都會將該 user_id 從 `_processing_users` 移除
- **避免使用者被永久鎖住**（例如程式發生未預期例外時）

---

## 與舊版的差異重點

| 項目 | 舊版 | 新版 |
|---|---|---|
| 頻道支援 | 單一頻道（全域變數） | 多頻道（傳入 `channel_config`） |
| 重疊處理保護 | 無 | `_processing_users` + `_state_lock` |
| 每日用量限制 | 無 | `_user_daily_usage` + `_usage_lock`，每日 10 次 |
| 回覆方式 | 全部用 `reply_message` | 先用 reply 回「請稍候」，後續用 `push_message` |
| 錯誤處理 | 無 `try/finally` | `try/finally` 確保 cleanup |
| API 客戶端建立 | 共用全域 `configuration` | 每次以 `channel_config` 建立 |

---

## 給同事做類似功能的重點歸納

| 環節 | 關鍵程式碼 | 說明 |
|---|---|---|
| **下載媒體** | `AsyncMessagingApiBlob(api_client).get_message_content(message_id)` | LINE 所有使用者上傳的圖片/影片/音檔都走這條 |
| **暫存檔案** | `uuid.uuid4()` 命名 + `os.makedirs` + `open().write()` | 用 UUID 避免檔名衝突，記得建目錄 |
| **AI 處理** | `ocr_image` / `score_essay` / `transcribe_audio` | 抽象在 `gemini.py`，可抽換成其他模型 |
| **條件過濾** | `is_group and user_id != channel_config["admin"]: return` | 群組內只讓管理員觸發，個人不限制 |
| **回覆結果** | 先 `reply_message` → 後續 `push_message` | reply_token 只能用一次，之後必須 push |
| **狀態管理** | `_processing_users` + `_user_daily_usage` + Lock | 用 `asyncio.Lock` 保護共享狀態，確保執行緒安全 |

---

## 做類似功能的快速上手

如果要**做類似但不同的功能**（例如使用者傳照片 → 辨識物品 → 回覆結果），只要：

1. 複製 `handle_image_message` 的整體架構
2. 把 `ocr_image` 換成你的辨識函數
3. 改回覆的訊息內容（`TextMessage` 或 `FlexMessage`）即可
