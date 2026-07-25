# 2026-07-25 新增 V2 評分模式：合併 scoring + md_to_html 為一次 Gemini 呼叫

## 改動動機

原先每次英文作文評分需調用 **3 次 Gemini API**：

1. OCR（圖片→文字）
2. Scoring（文字→Markdown 評分報告）
3. md_to_html（Markdown→HTML）

第 2、3 步本質上是同一批內容的兩次轉換，且 md_to_html 依賴 Gemini 而非程式庫做 Markdown→HTML，導致不必要的 API 成本與延遲。因此將 scoring 與 md_to_html 的 prompt 合併，讓 Gemini 一次輸出最終 HTML。

---

## 變更內容

### 1. 新增 `prompt/elementary_prompt_html.txt`

將 `elementary_prompt.txt`（評分規約）與 `MD_TO_HTML_PROMPT.txt`（HTML 結構規格）合併為單一 prompt：
- 保留 Role、Skills 1-5、Constraints 完全一致
- Output Format 從 Markdown 改為 HTML（含完整骨架、cor/dim 卡片、Chart.js 雷達圖）

### 2. `settings.yaml` — 新增 `scoring_mode` 參數

```yaml
scoring_mode: 'v1'  # 原始 3 次呼叫（V1）
scoring_mode: 'v2'  # 最佳化 2 次呼叫（V2）
```

由單一參數切換，無需修改程式碼或路由。

### 3. `config.py` — 載入新常數

- `SCORING_MODE` — 從 `settings.yaml` 讀取模式
- `ELEMENTARY_HTML_PROMPT` — 合併後的新 prompt

### 4. `gemini.py` — 新增 `score_essay_direct_html()`

- 與 `score_essay()` 相同邏輯，但：
  - 使用 `ELEMENTARY_HTML_PROMPT`（評分 + HTML 輸出）
  - 直接寫入 `output/{file_id}.html`，跳過 .md 中間格式
  - 套用 `_extract_html()` 清理 Gemini 回覆

### 5. `handlers.py` — V1/V2 分流 + 計時 log

```python
if SCORING_MODE == "v1":
    # 原始流程：score_essay + md_to_html
else:
    # 新流程：score_essay_direct_html
```

每階段以 `time.monotonic()` 計時，輸出 `[MODE] V1/V2 | ocr: ... | score: ...` log。

### 6. `main.py` — Root logger handler

`handlers.py` 使用 `logging.info()` 寫入 root logger，但原設定只為 uvicorn logger 加 handler，導致 log 被吞。補上 root logger 的 StreamHandler。

### 7. 修復 Unclosed client session

`handle_image_message()` 中多處 `_make_api()` 建立的 `AsyncApiClient` 未正確關閉，導致 aiohttp 噴 `Unclosed client session` 警告。改為單一 client 從頭用到尾並在 `finally` 中關閉。

---

## V1 vs V2 比較

| 項目 | V1 | V2 |
|------|:--:|:--:|
| Gemini 呼叫次數 | 3 次 | **2 次** |
| 中間檔案 | .md + .html | 僅 .html |
| 檔案 I/O | 寫 .md → 讀 .md → 寫 .html | 僅寫 .html |
| 流程時間 | OCR + scoring + md_to_html | OCR + scoring（含 HTML） |
| 輸出 HTML 結構 | md_to_html 產出 | scoring 直接產出 |
| 切換方式 | `scoring_mode: v1` | `scoring_mode: v2` |

比較方式：修改 `settings.yaml` 的 `scoring_mode`，restart service，上傳同一張圖片，比對 log 中的耗時與 output 目錄的 HTML 內容。

---

## 向後相容性

- `scoring_mode: 'v1'` 為原始流程，行為完全一致
- 兩種模式產出的 `.html` 檔案結構相同，LIFF 頁面與 scorepage endpoint 無需修改
- 路由、LINE Webhook、前端完全不受影響
