import yaml
import os
import re

# ── 支援 YAML 中 !include path 語法，將外部文字檔內容載入為字串 ──
_INCLUDE_RE = re.compile(r"^!include\s+(.+)$")

def _resolve(value):
    if isinstance(value, str) and (m := _INCLUDE_RE.match(value)):
        path = m.group(1).strip()
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return value

# ── 載入公開設定 ──
with open("settings.yaml", "r", encoding="utf-8") as f:
    conf = yaml.safe_load(f)

# ── 以機密設定（settings.local.yaml）覆蓋 API Key、Token 等 ──
local_path = "settings.local.yaml"
if os.path.exists(local_path):
    with open(local_path, "r", encoding="utf-8") as f:
        local_conf = yaml.safe_load(f)
    if local_conf:
        if "gemini_api_key" in local_conf:
            conf["gemini_api_key"] = local_conf["gemini_api_key"]
        if "line" in local_conf:
            for i, entry in enumerate(local_conf["line"]):
                if i < len(conf["line"]):
                    conf["line"][i].update(entry)

# ── 以下為所有模組共用的設定常數 ──

LINE_CONFIGS = conf["line"]

FLEX_WELCOME = conf["flex_welcome"]
FLEX_UPLOAD = conf["flex_upload"]
FLEX_GRADE = conf["flex_grade"]
FLEX_WAIT = conf["flex_wait"]

GEMINI_API_KEYS = conf["gemini_api_key"]
LLM_MODEL = conf["llm_model"]
GEMINI_OCR_PROMPT = conf["gemini_ocr_prompt"]
GEMINI_AUDIO_PROMPT = conf["gemini_audio_prompt"]
ELEMENTARY_PROMPT = _resolve(conf["elementary_prompt"])
MD_TO_HTML_PROMPT = _resolve(conf["MD_TO_HTML_PROMPT"])
