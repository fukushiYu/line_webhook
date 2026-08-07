# Webhook API Specification

## Purpose

`webhook-api` 負責對外暴露 LINE Bot 的 HTTP 入口。它是 FastAPI 應用程式的路由層，接收 LINE Platform 推送的 Webhook 事件、驗證請求來源、依事件類型分派至對應的 handler，並提供評分結果網頁與靜態資源的存取。此能力封裝於 `main.py`，是整個服務唯一的對外介面。

## Requirements

### Requirement: Webhook 端點簽章與頻道驗證

系統 SHALL 提供 `POST /webhook/line/{channel_idx}` 端點接收 LINE Platform 的 Webhook 請求，並在處理事件前完成頻道與簽章驗證。

#### Scenario: 缺少簽章標頭
- **WHEN** 請求沒有 `X-Line-Signature` 標頭
- **THEN** 系統回覆 HTTP 400，detail 為 `Missing Signature`

#### Scenario: 頻道索引超出範圍
- **WHEN** `channel_idx` 小於 0 或大於等於 `LINE_CONFIGS` 長度
- **THEN** 系統回覆 HTTP 400，detail 為 `Invalid channel`

#### Scenario: 簽章驗證失敗
- **WHEN** 請求帶有 `X-Line-Signature` 標頭，但與以該頻道 `channel_secret` 計算的 HMAC-SHA256 簽章不符
- **THEN** 系統回覆 HTTP 400，detail 為 `Invalid signature`

#### Scenario: 驗證通過
- **WHEN** 頻道索引有效且簽章驗證通過
- **THEN** 系統解析 JSON body 中的 `events[]` 並依事件類型分派處理，最後回覆 `OK`

### Requirement: 依事件類型分派處理

系統 SHALL 依 Webhook 事件類型，將圖片與音訊訊息交由背景任務處理、文字訊息與 Postback 以同步方式處理。

#### Scenario: 圖片訊息事件
- **WHEN** 事件類型為 `message` 且 `message.type` 為 `image`
- **THEN** 系統以 `asyncio.create_task` 呼叫 `handle_image_message`，不阻塞 Webhook 回應

#### Scenario: 音訊訊息事件
- **WHEN** 事件類型為 `message` 且 `message.type` 為 `audio`
- **THEN** 系統以 `asyncio.create_task` 呼叫 `handle_audio_message`，不阻塞 Webhook 回應

#### Scenario: 文字訊息事件
- **WHEN** 事件類型為 `message` 且 `message.type` 為 `text`
- **THEN** 系統以 `await` 同步呼叫 `handle_message`

#### Scenario: Postback 事件
- **WHEN** 事件類型為 `postback`
- **THEN** 系統以 `await` 同步呼叫 `handle_postback`

#### Scenario: 分派時傳入頻道設定
- **WHEN** 系統呼叫任一 handler
- **THEN** 系統傳入對應 `channel_config`（即 `LINE_CONFIGS[channel_idx]`），而非匯入全域 `LINE_CONFIGS`

### Requirement: 評分結果網頁服務

系統 SHALL 提供 `GET /webhook/scorepage` 端點回傳評分結果網頁，支援從 `liff.state` 參數解析報告 id。

#### Scenario: 提供 liff.state 且檔案存在
- **WHEN** 請求帶有 `liff.state` 參數，且可從中解析出 `id`，且 `output/{id}.html` 存在
- **THEN** 系統以 `FileResponse` 回傳該 HTML 檔案

#### Scenario: 提供 liff.state 但檔案不存在
- **WHEN** 請求帶有 `liff.state` 參數，可解析出 `id`，但 `output/{id}.html` 不存在
- **THEN** 系統回覆 HTML `Not Found`，狀態碼為 404

#### Scenario: 未提供 liff.state
- **WHEN** 請求沒有 `liff.state` 參數或解析不出 `id`
- **THEN** 系統回傳 `static/scorepage.html` 靜態預設頁

#### Scenario: liff.state 解析規則
- **WHEN** `liff.state` 值以 `?` 開頭（LIFF 自動附加格式，如 `?id=<uuid>`）
- **THEN** 系統去除開頭 `?` 後以 `parse_qs` 解析，並取 `id` 鍵的第一個值

### Requirement: 靜態資源與附屬端點

系統 SHALL 提供評分頁樣式與 favicon 端點。

#### Scenario: 提供樣式表
- **WHEN** 請求 `GET /webhook/style.css`
- **THEN** 系統以 `text/css` 的 `FileResponse` 回傳 `style.css`

#### Scenario: favicon 請求
- **WHEN** 請求 `GET /favicon.ico`
- **THEN** 系統回覆 HTTP 204 無內容，避免多餘的 404 日誌

### Requirement: 統一 uvicorn 日誌格式

系統 SHALL 於啟動時統一 root 與 `uvicorn`、`uvicorn.error`、`uvicorn.access` logger 的格式為「時間、層級、訊息」，層級設為 `INFO`，使 `handlers.py` 等模組的 `logging.info` 得以輸出。

#### Scenario: 應用啟動時設定 logger
- **WHEN** 應用啟動且上述 logger 被初始化
- **THEN** 每個 logger 以 `時間（%Y-%m-%d %H:%M:%S） 層級 訊息` 的格式輸出，層級設為 `INFO`

### Requirement: 設定重新載入端點

系統 SHALL 提供 `POST /config/reload` 端點，用於在服務運行中重新載入設定，無需重啟服務。端點 SHALL 以 `reload_token` 驗證請求來源。

#### Scenario: 提供正確 token 重新載入
- **WHEN** 請求 `POST /config/reload` 且 query 帶有與 `RELOAD_TOKEN` 相符的 token
- **THEN** 系統重新載入所有設定並回覆成功狀態

#### Scenario: token 錯誤或缺失
- **WHEN** 請求 `POST /config/reload` 且 token 缺失或與 `RELOAD_TOKEN` 不符
- **THEN** 系統回覆 HTTP 403，且不重新載入設定

#### Scenario: 重新載入後新設定生效
- **WHEN** 重新載入成功後有後續請求進入
- **THEN** 後續請求使用重新載入後的設定值（如 `llm_model`、`scoring_mode`、`GEMINI_API_KEYS`、flex 樣板）

### Requirement: 設定變更通知端點

系統 SHALL 提供 `POST /config/change` 端點，接收 GitHub 工作流程推送的設定/提示詞變更通知 JSON payload，並將事件內容記錄至 log。本階段僅記錄，SHALL NOT 執行任何重新載入或業務處理。

#### Scenario: 收到有效的變更通知
- **WHEN** 請求 `POST /config/change` 帶有 JSON body（含 `event`、`repository`、`commit`、`ref`、`file_url` 等欄位）
- **THEN** 系統以 `logging.info` 記錄事件內容，並回覆 HTTP 200

#### Scenario: body 非 JSON 或欄位缺失
- **WHEN** 請求 `POST /config/change` 的 body 無法解析為 JSON 或欄位不完整
- **THEN** 系統仍記錄收到的原始內容（不因解析失敗而中斷），並回覆 HTTP 200

#### Scenario: 本階段不觸發重新載入
- **WHEN** 請求 `POST /config/change` 成功被記錄
- **THEN** 系統不呼叫 `config.load()`、不修改任何設定、不觸發評分或推播等任何業務行為
