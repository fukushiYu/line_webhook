# Line Utilities Specification

## Purpose

`line-utilities` 是與 LINE Platform 通訊的基礎工具層，封裝於 `line_utils.py`。它提供 Webhook 簽章驗證與 LINE Messaging API 非同步客戶端的工廠函式。此能力不維護任何全域實例，所有函式皆由呼叫端傳入 `channel_config`，以支援多頻道架構。

## Requirements

### Requirement: Webhook 簽章驗證

系統 SHALL 提供 `verify_signature(channel_secret, body, signature) -> bool`，以 HMAC-SHA256 驗證 LINE Platform 發送的請求。

#### Scenario: 簽章相符
- **WHEN** 以 `channel_secret` 對 `body` 計算 HMAC-SHA256 並做 base64 編碼後的結果與 `signature` 相同
- **THEN** 函式回傳 `True`

#### Scenario: 簽章不符
- **WHEN** 計算結果與 `signature` 不同
- **THEN** 函式回傳 `False`

#### Scenario: 常數時間比較
- **WHEN** 比較簽章
- **THEN** 系統以 `hmac.compare_digest` 進行常數時間比較，避免計時攻擊

### Requirement: LINE API 客戶端工廠

系統 SHALL 提供 `get_line_api(channel_config) -> AsyncMessagingApi`，依傳入的頻道設定建立非同步 Messaging API 客戶端。

#### Scenario: 依頻道設定建立客戶端
- **WHEN** 呼叫端傳入包含 `channel_access_token` 的 `channel_config`
- **THEN** 系統以該 token 建立 `Configuration` 與 `AsyncApiClient`，並回傳 `AsyncMessagingApi` 實例
