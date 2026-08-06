# Config Management Specification

## Purpose

`config-management` 負責集中管理整個專案的全域設定。它在 `config.py` 啟動時一次性讀取公開設定 `settings.yaml`，以機密設定 `settings.local.yaml` 覆蓋 API Key、Token 與頻道機密，支援 `!include path` 語法將大型提示詞抽離為獨立檔案，最後匯出各模組共用的設定常數。此能力是「一切設定的單一來源」。

## Requirements

### Requirement: 載入公開設定

系統 SHALL 於模組匯入時讀取 `settings.yaml`，解析為設定字典。

#### Scenario: settings.yaml 存在
- **WHEN** 模組被匯入且 `settings.yaml` 存在
- **THEN** 系統以 `yaml.safe_load` 解析該檔案並建構設定字典

### Requirement: 覆蓋機密設定

系統 SHALL 於公開設定載入後，若 `settings.local.yaml` 存在則以其中的機密值覆蓋對應欄位。

#### Scenario: 覆蓋 gemini_api_key
- **WHEN** `settings.local.yaml` 存在且包含 `gemini_api_key` 鍵
- **THEN** 系統以機密設定覆蓋 `conf["gemini_api_key"]`

#### Scenario: 依索引覆蓋 line 頻道
- **WHEN** `settings.local.yaml` 存在且包含 `line` 清單
- **THEN** 系統以相同索引逐一 `update` 公開設定的 `line[i]`，且當機密清單索引超出公開清單長度時略過

#### Scenario: settings.local.yaml 不存在
- **WHEN** `settings.local.yaml` 不存在
- **THEN** 系統沿用 `settings.yaml` 的原始值，不產生錯誤

### Requirement: 支援 !include 語法

系統 SHALL 支援在 YAML 字串值中以 `!include path` 引用外部文字檔，並於載入時以檔案內容取代該值。

#### Scenario: 解析 !include
- **WHEN** 設定值為 `!include <path>` 字串
- **THEN** 系統讀取 `<path>` 檔案內容並以其取代原字串值

#### Scenario: 非 !include 值
- **WHEN** 設定值不以 `!include` 開頭
- **THEN** 系統保留原值不變

### Requirement: 匯出共用設定常數

系統 SHALL 匯出以下設定常數供各模組使用：`LINE_CONFIGS`、`FLEX_WELCOME`、`FLEX_UPLOAD`、`FLEX_GRADE`、`FLEX_WAIT`、`GEMINI_API_KEYS`、`LLM_MODEL`、`SCORING_MODE`、`MAX_OUTPUT_TOKENS`、`GEMINI_OCR_PROMPT`、`GEMINI_AUDIO_PROMPT`、`ELEMENTARY_PROMPT`、`ELEMENTARY_HTML_PROMPT`、`ELEMENTARY_HTML_DIRECT_PROMPT`、`MD_TO_HTML_PROMPT`。

#### Scenario: 頻道設定陣列
- **WHEN** 系統匯出 `LINE_CONFIGS`
- **THEN** 其值為 `settings.yaml` 中 `line` 清單，每個元素包含 `channel_secret`、`channel_access_token`、`admin`、`admin_prefix`、`liff_uri`、`endpoint_url`、`rich_menu_id`

#### Scenario: 評分模式預設值
- **WHEN** `settings.yaml` 未提供 `scoring_mode`
- **THEN** 系統將 `SCORING_MODE` 設為 `v1`

#### Scenario: 輸出 token 上限預設值
- **WHEN** `settings.yaml` 未提供 `max_output_tokens`
- **THEN** 系統將 `MAX_OUTPUT_TOKENS` 設為 `8192`

#### Scenario: 提示詞由外部檔案載入
- **WHEN** 系統匯出 `ELEMENTARY_PROMPT`、`ELEMENTARY_HTML_PROMPT`、`ELEMENTARY_HTML_DIRECT_PROMPT`、`MD_TO_HTML_PROMPT`
- **THEN** 其值分別為 `prompt/elementary_prompt.txt`、`prompt/elementary_prompt_html.txt`、`prompt/elementary_prompt_html_direct.txt`、`prompt/MD_TO_HTML_PROMPT.txt` 的檔案內容（經由 `_resolve` 處理）

### Requirement: Logo 網址參數

系統 SHALL 從設定中讀取全域 `logo_url` 參數並匯出為 `LOGO_URL` 常數；該參數為可選，未提供時預設為空字串。

#### Scenario: 讀取 logo_url
- **WHEN** `settings.yaml` 提供 `logo_url` 值
- **THEN** 系統將其匯出為 `LOGO_URL` 常數

#### Scenario: 未提供 logo_url
- **WHEN** `settings.yaml` 未提供 `logo_url`
- **THEN** 系統將 `LOGO_URL` 設為空字串，不產生錯誤

### Requirement: V3 直出 HTML 提示詞載入

系統 SHALL 從設定讀取 `elementary_html_direct_prompt`（以 `!include` 引用 `prompt/elementary_prompt_html_direct.txt`）並匯出為 `ELEMENTARY_HTML_DIRECT_PROMPT` 常數，供 V3 評分模式使用。

#### Scenario: 讀取 V3 提示詞
- **WHEN** `settings.yaml` 提供 `elementary_html_direct_prompt`（`!include` 語法）
- **THEN** 系統以 `_resolve` 讀取 `prompt/elementary_prompt_html_direct.txt` 內容並匯出為 `ELEMENTARY_HTML_DIRECT_PROMPT`

#### Scenario: 未提供 V3 提示詞
- **WHEN** `settings.yaml` 未提供 `elementary_html_direct_prompt`
- **THEN** 系統於匯入 `config.py` 時拋出 KeyError（V3 模式不可用，屬設定缺失錯誤，不靜默使用其他提示詞）
