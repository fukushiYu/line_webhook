# Essay Detection Specification

## Purpose

`essay-detection` 提供輕量級的規則過濾，封裝於 `english_essay.py`，用於判斷一段文字是否符合英文作文的基本格式。它透過字數、句數與大寫開頭比例三項規則，在呼叫昂貴的 Gemini 評分 API 前先阻擋明顯不是作文的輸入，以節省費用與時間。函式回傳 `(ok: bool, reason: str, cleaned: str)`，其中 `cleaned` 為去除前後空白後的文字。

## Requirements

### Requirement: 內容空白檢查

系統 SHALL 於文字去除前後空白後為空時判定不合格。

#### Scenario: 空白內容
- **WHEN** `text.strip()` 為空
- **THEN** 函式回傳 `ok=False`，`reason` 為 `文字內容為空白，無法判斷`

### Requirement: 字數檢查

系統 SHALL 於總詞數少於 30 時判定不合格。

#### Scenario: 字數不足
- **WHEN** `text.split()` 的詞數少於 30
- **THEN** 函式回傳 `ok=False`，`reason` 為 `字數不足（目前 N 詞，需至少 30 詞）`

#### Scenario: 字數足夠
- **WHEN** 詞數達 30 以上
- **THEN** 系統繼續進行後續檢查

### Requirement: 句子數量檢查

系統 SHALL 以 `.`、`!`、`?` 為分隔符統計句子數量，少於 2 句時判定不合格。

#### Scenario: 句子數量不足
- **WHEN** 以 `[.!?]+` 分割後的有效句子少於 2 句
- **THEN** 函式回傳 `ok=False`，`reason` 為 `句子數量不足（目前 N 句，需至少 2 句）`

### Requirement: 大寫開頭比例檢查

系統 SHALL 於大寫開頭句子佔總句數比例低於 50% 時判定不合格。

#### Scenario: 大寫比例不足
- **WHEN** 大寫開頭句數除以總句數小於 0.5
- **THEN** 函式回傳 `ok=False`，`reason` 為 `大部分句子未以大寫開頭，不似英文作文格式`

#### Scenario: 大寫比例達標
- **WHEN** 大寫開頭句數除以總句數達 0.5 以上
- **THEN** 函式回傳 `ok=True`，`reason` 為空字串，`cleaned` 為去除前後空白的原文字
