# 2026-08-06 新增 V3 評分模式：OCR + 評分 + HTML 合併為一次 Gemini 呼叫

## 改動動機

原先英文作文評分需調用 Gemini API：

1. V1：**3 次**（OCR → scoring → md_to_html）
2. V2：**2 次**（OCR → scoring 直出 HTML）

Gemini 本身具備多模態能力，可一次讀取圖片並直接輸出最終 HTML。V3 將 OCR、評分與 HTML 輸出合併為**單次**呼叫，進一步降低 API 成本與端到端延遲。原 V1 / V2 模式保留，以 `settings.yaml` 的 `scoring_mode` 切換。

---

## 變更內容

### 1. 新增 `prompt/elementary_prompt_html_direct.txt`

以 `elementary_prompt_html.txt`（評分規約 + HTML 輸出格式）為基礎，於開頭追加：
- **OCR 指示**：直接辨識附圖作文、不得增刪改原文、字跡不清提醒。
- **非作文回退規則**：當圖片非英文作文時，輸出「這不是一篇英文作文」的固定回退 HTML，不進行評分（取代 V1/V2 的 Python `is_english_essay()` 檢測）。

### 2. `settings.yaml` — 新增設定鍵與 `scoring_mode: v3`

```yaml
elementary_html_direct_prompt: '!include prompt/elementary_prompt_html_direct.txt'
# scoring_mode: 'v3'  # V3: 1 次 Gemini（圖片 → OCR + 評分 + 直出 .html）
```

### 3. `config.py` — 載入新常數

- `ELEMENTARY_HTML_DIRECT_PROMPT` — V3 模式用的合併 prompt

### 4. `gemini.py` — 新增 `score_essay_from_image()`

- 以 `_call_gemini(filepath, "image/jpeg", ELEMENTARY_HTML_DIRECT_PROMPT)` 將圖片 base64 內嵌單次呼叫
- 回覆經 `_extract_html()` 清理 + `_inject_logo()` 注入後直接寫入 `output/{file_id}.html`
- Gemini 回覆缺少有效欄位時回傳 `<p>無法評分</p>`

### 5. `handlers.py` — V1/V2/V3 分流

```python
if SCORING_MODE == "v3":
    # 跳過 ocr_image 與 is_english_essay，單次呼叫 score_essay_from_image
else:
    # V1/V2 原流程（OCR → is_english_essay → score_essay 或 score_essay_direct_html）
```

- V3 模式輸出 `[MODE] V3 | score_essay_from_image: X.XXXs` 計時 log
- v1/v2 分支保持原樣，推播 `FLEX_GRADE` 流程三模式共用

---

## V1 vs V2 vs V3 比較

| 項目 | V1 | V2 | V3 |
|------|:--:|:--:|:--:|
| Gemini 呼叫次數 | 3 次 | 2 次 | **1 次** |
| 中間檔案 | .md + .html | 僅 .html | 僅 .html |
| 檔案 I/O | 寫 .md → 讀 .md → 寫 .html | 僅寫 .html | 僅寫 .html |
| 流程時間 | OCR + scoring + md_to_html | OCR + scoring（含 HTML） | 讀圖 + scoring（含 HTML） |
| 作文檢測 | Python `is_english_essay` | Python `is_english_essay` | 模型依提示詞輸出回退 HTML |
| 切換方式 | `scoring_mode: v1` | `scoring_mode: v2` | `scoring_mode: v3` |

比較方式：修改 `settings.yaml` 的 `scoring_mode`，restart service，上傳同一張圖片，比對 log 中的耗時與 output 目錄的 HTML 內容。

---

## 向後相容性

- `scoring_mode: 'v1'` 與 `'v2'` 為原始流程，行為完全一致
- 三種模式產出的 `.html` 檔案結構相同，LIFF 頁面與 scorepage endpoint 無需修改
- 路由、LINE Webhook、前端完全不受影響
- 若 `settings.yaml` 未設定 `elementary_html_direct_prompt`，`config.py` 匯入時拋出 KeyError（V3 模式不可用，屬設定缺失，不靜默使用其他提示詞）
