# Gemini Integration Specification

## Purpose

`gemini-integration` 封裝所有與 Google Gemini API 的互動，位於 `gemini.py`。它對外提供 OCR 辨識、語音轉寫、作文評分（V1 存 `.md`）、評分直出 HTML（V2）與 Markdown 轉 HTML 等函式，並從 Gemini 回覆中擷取乾淨的 HTML。所有呼叫皆以 `aiohttp` 非同步執行、隨機選取 `GEMINI_API_KEYS` 中的一組 key，並帶入 `MAX_OUTPUT_TOKENS` 防止輸出截斷。

## Requirements

### Requirement: 多媒體 Gemini 呼叫

系統 SHALL 提供 `_call_gemini(filepath, mime_type, prompt)` 底層函式，將檔案以 base64 內嵌於請求中呼叫 Gemini `generateContent` 端點。

#### Scenario: 組建請求
- **WHEN** 呼叫 `_call_gemini`
- **THEN** 系統讀取檔案並以 base64 編碼，以 `random.choice` 選取一組 API key，組成含 `text`（prompt）與 `inline_data`（mime_type、base64）的 payload，並帶入 `maxOutputTokens`

#### Scenario: 成功解析
- **WHEN** Gemini 回覆含 `candidates[0].content.parts[0].text`
- **THEN** 系統回傳該文字

#### Scenario: 解析失敗
- **WHEN** Gemini 回覆缺少 `candidates`、`content` 或 `parts` 欄位
- **THEN** 系統回傳 `無法辨識內容`

### Requirement: OCR 與語音轉寫

系統 SHALL 提供 `ocr_image(filepath)` 與 `transcribe_audio(filepath, mime_type)`，分別以 `GEMINI_OCR_PROMPT` 與 `GEMINI_AUDIO_PROMPT` 呼叫底層函式。

#### Scenario: 圖片 OCR
- **WHEN** 呼叫 `ocr_image`
- **THEN** 系統以 `image/jpeg` 的 MIME type 與 `GEMINI_OCR_PROMPT` 呼叫 `_call_gemini`

#### Scenario: 語音轉寫
- **WHEN** 呼叫 `transcribe_audio`
- **THEN** 系統以傳入的 `mime_type` 與 `GEMINI_AUDIO_PROMPT` 呼叫 `_call_gemini`

### Requirement: 純文字評分呼叫與 .md 寫入

系統 SHALL 提供 `_call_gemini_text(prompt, text, file_id)` 底層函式，以純文字呼叫 Gemini 並將結果寫入 `output/{file_id}.md`。

#### Scenario: 成功寫入 .md
- **WHEN** Gemini 回覆含有效文字
- **THEN** 系統確保 `output` 目錄存在，並將結果寫入 `output/{file_id}.md`

#### Scenario: 解析失敗
- **WHEN** Gemini 回覆缺少有效欄位
- **THEN** 系統回傳 `無法評分`

### Requirement: 作文評分（V1）

系統 SHALL 提供 `score_essay(text, file_id)`，以 `ELEMENTARY_PROMPT` 對學生的文章評分，並將結果寫入 `.md` 檔。

#### Scenario: V1 評分
- **WHEN** 呼叫 `score_essay`
- **THEN** 系統以 `ELEMENTARY_PROMPT` 與文字 `學生的文章：{text}` 呼叫 `_call_gemini_text`，產出 `output/{file_id}.md`

### Requirement: 評分直出 HTML（V2）

系統 SHALL 提供 `score_essay_direct_html(text, file_id)`，以 `ELEMENTARY_HTML_PROMPT` 一次呼叫完成評分與 HTML 轉換，經 `_extract_html` 清理後寫入 `output/{file_id}.html`，跳過 `.md` 中間格式。

#### Scenario: V2 成功寫入 HTML
- **WHEN** Gemini 回覆含有效文字
- **THEN** 系統以 `_extract_html` 清理後寫入 `output/{file_id}.html`

#### Scenario: V2 解析失敗
- **WHEN** Gemini 回覆缺少有效欄位
- **THEN** 系統回傳 `<p>無法評分</p>`

### Requirement: 作文評分直出 HTML（V3 單次呼叫）

系統 SHALL 提供 `score_essay_from_image(filepath, file_id)`，以圖片內嵌（base64）方式**單次**呼叫 Gemini，一次完成 OCR、評分與 HTML 輸出；回覆經 `_extract_html` 清理並套用 Logo 注入後寫入 `output/{file_id}.html`，跳過 OCR 文字與 `.md` 中間格式。

#### Scenario: V3 成功寫入 HTML
- **WHEN** 呼叫 `score_essay_from_image` 且 Gemini 回覆含有效文字
- **THEN** 系統以 `_call_gemini` 將圖片以 `image/jpeg` 內嵌、以 V3 提示詞單次呼叫 Gemini，並以 `_extract_html` 清理後寫入 `output/{file_id}.html`（含 Logo 注入規則）

#### Scenario: V3 解析失敗
- **WHEN** Gemini 回覆缺少 `candidates`、`content` 或 `parts` 欄位
- **THEN** 系統回傳 `<p>無法評分</p>`

#### Scenario: V3 非英文作文回退
- **WHEN** 圖片內容非英文作文（由模型依 V3 提示詞判斷）
- **THEN** 系統依提示詞輸出固定回退 HTML，內容說明「這不是一篇英文作文」，並照常寫入 `output/{file_id}.html`

#### Scenario: V3 Logo 注入
- **WHEN** V3 模式產出評分報告 HTML
- **THEN** 系統對產出的 HTML 套用與 V1/V2 相同的 `_inject_logo` Logo 注入規則

### Requirement: Markdown 轉 HTML（V1）

系統 SHALL 提供 `md_to_html(file_id)`，讀取 `output/{file_id}.md` 後以 `MD_TO_HTML_PROMPT` 呼叫 Gemini，經 `_extract_html` 清理後寫入 `output/{file_id}.html`。

#### Scenario: 成功轉換
- **WHEN** `output/{file_id}.md` 存在且 Gemini 回覆有效文字
- **THEN** 系統以 `_extract_html` 清理後寫入 `output/{file_id}.html`

#### Scenario: 轉換失敗
- **WHEN** Gemini 回覆缺少有效欄位
- **THEN** 系統回傳 `<p>轉換失敗</p>`

### Requirement: HTML 內容擷取

系統 SHALL 提供 `_extract_html(raw)`，從 Gemini 回覆中擷取第一組 `<!DOCTYPE`、`<!doctype` 或 `<html` 標籤起的內容，並移除結尾的 markdown code fence。

#### Scenario: 移除開頭雜訊
- **WHEN** 回覆中含有 `<!DOCTYPE`、`<!doctype` 或 `<html` 標記
- **THEN** 系統自該標記起保留其後內容

#### Scenario: 移除結尾 code fence
- **WHEN** 擷取後內容以 ``` 結尾
- **THEN** 系統以 `rsplit("```", 1)` 去除該 code fence

### Requirement: 評分報告注入可設定 Logo

系統 SHALL 在產出評分報告 HTML 時，於內容區左上角注入可由設定指定的 Logo 圖片；Logo 網址為參數，未設定時不顯示任何 Logo。

#### Scenario: 有設定 logo_url 時注入
- **WHEN** 設定中存在非空的 `logo_url`，且系統產出評分報告 HTML
- **THEN** 系統在 HTML 的 `<article>` 開頭注入一個指向 `logo_url` 的 `<img>` 元素，使 Logo 顯示於內容區左上角並隨內容捲動

#### Scenario: 未設定 logo_url
- **WHEN** 設定中沒有 `logo_url` 或其值為空
- **THEN** 系統原樣輸出 HTML，不注入任何 Logo 元素

#### Scenario: 高度為 H1 的三倍
- **WHEN** 系統注入 Logo 元素
- **THEN** Logo 的高度約為頁面 H1 文字高度的 3 倍（約 `6rem`，寬螢幕為 `6.75rem`），寬度依圖片比例自動調整

#### Scenario: V1 模式亦套用
- **WHEN** `SCORING_MODE` 為 `v1`（經 `md_to_html` 產出 HTML）
- **THEN** 系統對產出的 HTML 套用相同的 Logo 注入規則

#### Scenario: V2 模式亦套用
- **WHEN** `SCORING_MODE` 為 `v2`（經 `score_essay_direct_html` 產出 HTML）
- **THEN** 系統對產出的 HTML 套用相同的 Logo 注入規則
