# 2026-07-24 重構：scorepage 改為只接受 `liff.state` 參數

## 改動動機

原先 Flex Message 按鈕的 URI 指向 `endpoint_url?id=<uuid>`（即直接指向 hook 伺服器的 `/webhook/scorepage`），但這繞過了 LINE LIFF 的 `liff.state` 機制，導致：

- LIFF 無法在評分頁面中取得使用者資訊（如 `getProfile()`、`getIDToken()`）
- 未來若需要在使用者開啟評分頁時驗證身份或取得 LINE 個人資料，將無法實作

因此將 URI 改回指向 `liff_uri`，由 LIFF 自動將 query parameters 封裝為 `liff.state` 傳入 scorepage。

---

## 變更內容

### 1. `main.py` — scorepage 路由參數

**更改前**（直接接收 `id` query param）:

```python
@app.get("/webhook/scorepage")
async def score_page(id: str = Query(None)):
    if id:
        filepath = os.path.join("output", f"{id}.html")
        if os.path.exists(filepath):
            return FileResponse(filepath)
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)
    return FileResponse("static/scorepage.html")
```

**更改後**（接收 `liff.state`，從中解析 `id`）:

```python
@app.get("/webhook/scorepage")
async def score_page(liff_state: str = Query(None, alias="liff.state")):
    if liff_state:
        from urllib.parse import parse_qs
        params = parse_qs(liff_state.lstrip("?"))
        id = params.get("id", [None])[0]
        if id:
            filepath = os.path.join("output", f"{id}.html")
            if os.path.exists(filepath):
                return FileResponse(filepath)
            return HTMLResponse("<h1>Not Found</h1>", status_code=404)
    return FileResponse("static/scorepage.html")
```

關鍵差異：

| 項目 | 舊版 | 新版 |
|------|------|------|
| Query 參數 | `?id=<uuid>` | `?liff.state=?id=<uuid>` |
| 參數別名 | `id` | `liff.state`（FastAPI 透過 `alias` 支援含點的參數名） |
| id 取得 | 直接從 query param 取得 | 從 `liff.state` 字串中 `parse_qs` 解析 |
| FastAPI 語法 | `Query(None)` | `Query(None, alias="liff.state")` |

> FastAPI 預設不允許 query parameter 名稱包含 `.`，必須透過 `Query(alias=...)` 指定別名才能正確接收 `liff.state`。

### 2. `handlers.py` — Flex Message 按鈕 URI

**更改前**:

```python
flex_dict["body"]["contents"][1]["action"]["uri"] = f"{channel_config['endpoint_url']}?id={basename}"
```

**更改後**:

```python
flex_dict["body"]["contents"][1]["action"]["uri"] = f"{channel_config['liff_uri']}?id={basename}"
```

| 項目 | 舊版 | 新版 |
|------|------|------|
| 目標 URI | `endpoint_url?id=<uuid>`（直連 hook） | `liff_uri?id=<uuid>`（走 LIFF） |
| 作用 | 跳過 LIFF 直接顯示 | 經 LIFF 包裝，自動產生 `liff.state` |

### 3. `README.md` — 文件更新

同步更新了以下三處：
- 功能一覽的 LIFF 評分頁說明（line 41）
- `scorepage` 端點說明改為「從 `liff.state` 解析 `id`」（line 194）
- 核心架構的靜態資源服務說明（line 15）

---

## 資料流變更

```
                   使用者點擊 Flex Message 按鈕
                           │
          ┌────────────────┴────────────────┐
          │ 舊版                            │ 新版
          ▼                                 ▼
  endpoint_url?id=<uuid>           liff_uri?id=<uuid>
          │                                 │
          ▼                                 │
  FastAPI 直接回傳 HTML              LINE LIFF 開啟
          │                                 │
          │                           LIFF 自動產生
          │                           liff.state = "?id=<uuid>"
          │                                 │
          │                                 ▼
          │                     FastAPI 接收 ?liff.state=?id=<uuid>
          │                                 │
          │                           parse_qs 取出 id
          │                                 │
          └────────────┬────────────────────┘
                       ▼
              回傳 output/{id}.html
```

---

## 向後相容性

- **舊連結**：如果外部已有直接指向 `endpoint_url?id=<uuid>` 的連結（例如瀏覽器書籤），這些連結會 **失效**（因為現在只接受 `liff.state`，`id` 參數會被忽略）。
- **新連結**：只有透過 LINE LIFF 開啟（即點擊 Flex Message 上的按鈕）的請求才會攜帶 `liff.state`，正常運作。

這是預期行為 — 評分報告本應只在 LIFF 環境中開啟。
