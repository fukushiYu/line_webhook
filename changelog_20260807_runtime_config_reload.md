# 2026-08-07 新增設定熱更新：`POST /config/reload`（不重啟即套用 YAML 變更）

## 改動動機

原先 `config.py` 只在模組匯入時一次性讀取 `settings.yaml`，且各模組以 `from config import X` 快照方式取值。任何 YAML 設定變動（如 `llm_model`、`scoring_mode`、prompt、`logo_url`）都必須**重啟服務**才會生效，中斷線上使用者。

本次變更讓設定可在運行中重新載入：改完 YAML 後呼叫一次 reload 端點（或 `bash menu.sh reload`）即全部生效。

---

## 變更內容

### 1. `config.py` — 包裝為可重複執行的 `load()`

- 將「讀取 `settings.yaml` → 以 `settings.local.yaml` 覆蓋機密 → `_resolve` 解析 `!include` → 匯出常數」的邏輯包進 `def load():`
- 以 `globals().update({...})` 原地更新所有設定常數（含 `LINE_CONFIGS`、Flex 樣板、`GEMINI_API_KEYS`、prompts、`LOGO_URL` 等）
- 模組底部保留 `load()` 呼叫一次，import 行為不變
- 新增 `RELOAD_TOKEN`（取自 `settings.local.yaml` 的 `reload_token`，未提供時為空字串）

### 2. 各模組改為動態取值 `config.XXX`

| 模組 | 變更 |
|---|---|
| `main.py` | `from config import LINE_CONFIGS` → `import config`，webhook 內改 `config.LINE_CONFIGS` |
| `handlers.py` | `from config import (SCORING_MODE, FLEX_*)` → `import config`，使用處改 `config.XXX` |
| `gemini.py` | `from config import ...`（10 個常數）→ `import config`，函式內改 `config.XXX` |

> 刻意**不採用** `importlib.reload(handlers)`：那會把 `_user_daily_usage`（每日上限）與 `_processing_users`（處理中鎖定）重置，造成狀態 bug。動態取值即可在保留狀態的前提下套用新設定。

### 3. `main.py` — 新增 reload 端點

```python
@app.post("/config/reload")
async def config_reload(token: str = Query(...)):
    if token != config.RELOAD_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    config.load()
    return {"ok": True, "reloaded": True}
```

- token 以 query 參數傳遞，與 `settings.local.yaml` 的 `reload_token` 相符才執行；不符回 HTTP 403

### 4. `settings.local.yaml` — 新增 `reload_token`

```yaml
reload_token: 'your-reload-token'
```

（gitignored，不進公開 repo；實際值請依部署環境設定）

### 5. `menu.sh` — 新增 reload 指令

- CLI：`bash menu.sh reload`（自動讀取 `reload_token` 並呼叫 reload 端點）
- 互動選單新增「4) 重新載入設定」，原選項順移

---

## 使用方式

```bash
# 改完 settings.yaml / settings.local.yaml 後：
curl -X POST 'http://localhost:9000/config/reload?token=<reload_token>'
# 或
bash menu.sh reload
```

回覆 `{"ok": true, "reloaded": true}`（HTTP 200）；token 錯誤回 403。

---

## 行為與相容性

- reload 只更新 `config` 模組常數，不重啟 process、不重置每日用量與處理中狀態
- import 時仍會自動載入一次，與舊版行為一致
- 若 `reload_token` 未設定，reload 端點無法通過驗證（預期內，屬部署設定）
- `FLEX_GRADE` 等 Flex 樣板在 reload 後換成由 YAML 重建的新 dict，`handlers.py` 填入 LIFF URI 的原地修改不會殘留
- 已同步更新 `openspec/specs/config-management` 與 `openspec/specs/webhook-api` 主規格
