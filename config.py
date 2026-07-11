import yaml

with open("settings.yaml", "r", encoding="utf-8") as f:
    conf = yaml.safe_load(f)

CHANNEL_SECRET = conf["channel_secret"]
CHANNEL_ACCESS_TOKEN = conf["channel_access_token"]

FLEX_WELCOME = conf["flex_welcome"]
FLEX_UPLOAD = conf["flex_upload"]
FLEX_GRADE = conf["flex_grade"]

ADMIN = conf["admin"]
ADMIN_PREFIX = conf["admin_prefix"]
LIFF_URI = conf["liff_uri"]

GEMINI_API_KEYS = conf["gemini_api_key"]
LLM_MODEL = conf["llm_model"]
GEMINI_PROMPT = conf["gemini_prompt"]
GEMINI_AUDIO_PROMPT = conf["gemini_audio_prompt"]

RICH_MENU_A_ID = "richmenu-xxxxxxxxxxxxxx"
