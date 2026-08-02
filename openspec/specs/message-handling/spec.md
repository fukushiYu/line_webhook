# Message Handling Specification

## Purpose

`message-handling` 是整個服務的商業邏輯層，封裝於 `handlers.py`。它處理 LINE 的文字指令、圖片上傳（核心功能）、語音轉寫與 Postback 事件，串接 `config.py` 的 Flex 模板、`gemini.py` 的 AI 服務與 `english_essay.py` 的作文檢測。所有 handler 皆接收 `channel_config: dict` 參數以支援多頻道，並透過 `_make_api()` 依該頻道建立非同步 API 客戶端。

## Requirements

### Requirement: 文字指令處理

系統 SHALL 於收到文字訊息時，依使用者輸入（群組情境需管理員以 `admin_prefix` 前綴觸發）分派指令並回應對應訊息。

#### Scenario: 群組中非管理員
- **WHEN** 訊息來自群組，且訊息未以 `admin_prefix` 開頭或發送者非該頻道 `admin`
- **THEN** 系統不處理該訊息，直接回傳

#### Scenario: 群組中管理員帶前綴
- **WHEN** 訊息來自群組，且發送者為該頻道 `admin` 且訊息以 `admin_prefix` 開頭
- **THEN** 系統去除前綴後以小寫比對指令並執行

#### Scenario: 指令 grade
- **WHEN** 處理後文字為 `grade`
- **THEN** 系統回傳 `FLEX_GRADE` Flex Message，且其按鈕 URI 設為該頻道的 `liff_uri`

#### Scenario: 指令 welcome
- **WHEN** 處理後文字為 `welcome`
- **THEN** 系統回傳 `FLEX_WELCOME` Flex Message

#### Scenario: 指令 upload
- **WHEN** 處理後文字為 `upload`
- **THEN** 系統回傳 `FLEX_UPLOAD` Flex Message

#### Scenario: 指令 menu / 選單
- **WHEN** 處理後文字為 `menu` 或 `選單`
- **THEN** 系統以 `link_rich_menu_id_to_user` 將該頻道的 `rich_menu_id` 連結至使用者，並回覆文字 `特殊圖文選單已為您開啟！`

#### Scenario: 未定義指令
- **WHEN** 處理後文字不符任何指令
- **THEN** 系統回傳 Echo 訊息，內容含原始文字、User ID，且若來源為群組則附帶 Group ID

### Requirement: 圖片上傳權限與重疊保護

系統 SHALL 於處理圖片訊息前檢查來源權限與是否已有圖片正在處理，避免重疊處理與非管理員在群組上傳。

#### Scenario: 群組非管理員上傳
- **WHEN** 圖片訊息來自群組且發送者非該頻道 `admin`
- **THEN** 系統直接回傳，不處理圖片

#### Scenario: 重疊處理
- **WHEN** 使用者已有圖片在處理中（位於 `_processing_users` 集合）
- **THEN** 系統回覆文字 `您有圖片正在處理中，請稍候再上傳。` 並結束

#### Scenario: 開始處理時標記
- **WHEN** 使用者無進行中的圖片
- **THEN** 系統在 `_state_lock` 保護下將 `user_id` 加入 `_processing_users`，處理結束後於 `finally` 中移除

### Requirement: 每日用量上限

系統 SHALL 以 Asia/Taipei 時區為每位使用者施行每日圖片評分次數上限（預設 10 次），超過即拒絕。

#### Scenario: 未達上限
- **WHEN** 使用者在當天（Asia/Taipei）的用量未達 10 次
- **THEN** 系統在 `_usage_lock` 保護下遞增該使用者的當日計數並繼續處理

#### Scenario: 已達上限
- **WHEN** 使用者在當天（Asia/Taipei）的用量已達 10 次
- **THEN** 系統回覆文字 `您今天已達每日使用上限，請明天再來。` 並結束

#### Scenario: 跨日重置
- **WHEN** 使用者先前有紀錄但其日期不等於今天
- **THEN** 系統以 `{"date": today, "count": 1}` 重設該使用者紀錄

### Requirement: 圖片處理流程

系統 SHALL 於圖片通過權限、重疊與用量檢查後，依序執行「回覆請稍候 → 下載圖片 → 存檔 → OCR → 英文作文檢測 → 評分 → 推播結果」，全程使用單一 `AsyncApiClient` 並於 `finally` 中關閉。

#### Scenario: 立即回覆請稍候
- **WHEN** 進入正式處理
- **THEN** 系統以 `reply_message` 回覆 `FLEX_WAIT` Flex Message（佔用 `reply_token`）

#### Scenario: 下載與存檔
- **WHEN** 已回覆請稍候
- **THEN** 系統以 `AsyncMessagingApiBlob.get_message_content` 下載圖片，以新 `uuid4()` 命名並存入 `images/{uuid}.jpg`

#### Scenario: OCR 與計時
- **WHEN** 圖片已存檔
- **THEN** 系統呼叫 `gemini.ocr_image`，並以 `logging.info` 輸出 `[MODE] ... | ocr: X.XXXs` 耗時

#### Scenario: 作文檢測失敗
- **WHEN** `is_english_essay` 回傳 `ok=False`
- **THEN** 系統以 `push_message` 推播文字 `這不是一篇英文作文：{reason}` 並結束，不進行評分

#### Scenario: 評分模式 v1
- **WHEN** `SCORING_MODE` 為 `v1`
- **THEN** 系統依序呼叫 `score_essay`（產出 `output/{id}.md`）與 `md_to_html`（產出 `output/{id}.html`），並輸出各階段耗時日誌（共 3 次 Gemini 呼叫）

#### Scenario: 評分模式 v2
- **WHEN** `SCORING_MODE` 非 `v1`（預設 `v2`）
- **THEN** 系統呼叫 `score_essay_direct_html` 直接產出 `output/{id}.html`，並輸出單一階段耗時日誌（共 2 次 Gemini 呼叫）

#### Scenario: 推播評分結果
- **WHEN** 評分完成
- **THEN** 系統以 `push_message` 推播 `FLEX_GRADE` Flex Message，按鈕 URI 設為 `{channel_config['liff_uri']}?id={basename}`

### Requirement: 語音轉寫

系統 SHALL 於收到音訊訊息時（群組限管理員），依 MIME type 決定副檔名存檔，呼叫 Gemini 轉寫後以文字回覆使用者。

#### Scenario: 群組非管理員語音
- **WHEN** 音訊訊息來自群組且發送者非該頻道 `admin`
- **THEN** 系統直接回傳，不處理

#### Scenario: 下載並依 MIME 存檔
- **WHEN** 音訊通過權限檢查
- **THEN** 系統以 `get_message_content_with_http_info` 取得 raw data 與 Content-Type，依 `AUDIO_EXT_MAP` 對應副檔名（無對應時預設 `.m4a`）存入 `audios/{uuid}{ext}`

#### Scenario: 轉寫並回覆
- **WHEN** 音訊已存檔
- **THEN** 系統呼叫 `gemini.transcribe_audio`，以 `reply_message` 回覆轉寫文字，並關閉 `AsyncApiClient`

### Requirement: Postback 事件處理

系統 SHALL 提供 `handle_postback(event, channel_config)` 作為 Postback 事件的擴充點。

#### Scenario: 目前無行為
- **WHEN** 收到 Postback 事件
- **THEN** 系統不執行任何動作（當前為空實作，保留介面供未來擴充）
