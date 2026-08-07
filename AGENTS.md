# AGENTS.md — Hook (Blossom Academy LINE Bot)

## Start / Dev

- **Serve**: `uvicorn main:app --port 9000` (uses venv at repo root)
- **Manage**: `bash menu.sh` (start/stop/restart/reload/log via PID at `.hook.pid`)
- **Config split**: `settings.yaml` (public, tracked) + `settings.local.yaml` (secrets, gitignored). `config.py` merges them at import time and exposes `load()` for runtime reload without restart.
- **Config reload**: after editing YAML, call `POST /config/reload?token=<reload_token>` or run `bash menu.sh reload` to re-read settings. `reload_token` lives in `settings.local.yaml`.
- **Prompt files live in `prompt/`** and are loaded via `!include path` syntax in `settings.yaml`.

## Architecture

- **Entrypoint**: `main.py` — FastAPI app exposing `POST /webhook/line/{channel_idx}`.
- **Multi-channel**: `channel_idx` indexes into `LINE_CONFIGS` array from `config.py` (derived from `settings.yaml` `line:` list). Each channel has its own `channel_secret`, `channel_access_token`, `admin`, `admin_prefix`, `liff_uri`, `rich_menu_id`.
- **Image processing** (core feature): runs as `asyncio.create_task` (non-blocking). Text messages and postbacks are synchronous (`await`).
- **Scoring modes**: `scoring_mode: v3` (1 Gemini call: image → direct HTML, skips OCR/essay-detection, non-essay handled by model) or `v2` (default, 2 Gemini calls: OCR → direct HTML) or `v1` (3 calls: OCR → scoring .md → md_to_html). Set in `settings.yaml`.
- **Gemini keys**: `GEMINI_API_KEYS` is an array; one is chosen at random per call (simple round-robin via `random.choice`).

## Important conventions

- Every handler receives `channel_config: dict` — do NOT import LINE_CONFIGS in handlers; use the passed config.
- Image messages: reply first with "please wait" flex (uses `reply_token`), then push results later via `push_message` (reply_token consumed).
- Daily limit: 10 images/user/day, Asia/Taipei timezone. Overlap protection via `_processing_users` asyncio.Lock.
- `_extract_html()` strips Markdown code fences from Gemini output — necessary for both V1 and V2 HTML paths.
- No tests, no linter, no type checker configured.
