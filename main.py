import json,asyncio,os,logging
from fastapi import FastAPI, Request, HTTPException, Header, Query
from fastapi.responses import FileResponse, HTMLResponse, Response
from linebot.v3.webhooks import MessageEvent, PostbackEvent
from config import LINE_CONFIGS
from line_utils import verify_signature
from handlers import handle_message, handle_image_message, handle_audio_message, handle_postback

# ── uvicorn 日誌統一格式（時間、層級、訊息） ──
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _logger = logging.getLogger(_name)
    _logger.handlers.clear()
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)

app = FastAPI()


# ── 瀏覽器 favicon 請求直接回 204 無內容 ──
@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


# ── LINE Webhook 入口（支援多頻道，channel_idx 對應 settings.yaml 的 line 陣列索引） ──
@app.post("/webhook/line/{channel_idx}")
async def webhook(channel_idx: int, request: Request, x_line_signature: str = Header(None)):
    if x_line_signature is None:
        raise HTTPException(status_code=400, detail="Missing Signature")
    if channel_idx < 0 or channel_idx >= len(LINE_CONFIGS):
        raise HTTPException(status_code=400, detail="Invalid channel")
    body = await request.body()
    channel_config = LINE_CONFIGS[channel_idx]
    if not verify_signature(channel_config["channel_secret"], body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # ── 依事件類型分派：圖片（背景執行）、音訊（背景執行）、文字、Postback ──
    body_dict = json.loads(body.decode("utf-8"))
    for event_dict in body_dict.get("events", []):
        if event_dict.get("type") == "message":
            msg_type = event_dict.get("message", {}).get("type")
            if msg_type == "image":
                asyncio.create_task(handle_image_message(MessageEvent.from_dict(event_dict), channel_config))
            elif msg_type == "audio":
                asyncio.create_task(handle_audio_message(MessageEvent.from_dict(event_dict), channel_config))
            elif msg_type == "text":
                await handle_message(MessageEvent.from_dict(event_dict), channel_config)
        elif event_dict.get("type") == "postback":
            await handle_postback(PostbackEvent.from_dict(event_dict), channel_config)
    return "OK"


# ── 評分報告頁面：有 ?id= 則回傳對應 HTML，無則顯示靜態預設頁 ──
@app.get("/webhook/scorepage")
async def score_page(id: str = Query(None)):
    if id:
        filepath = os.path.join("output", f"{id}.html")
        if os.path.exists(filepath):
            return FileResponse(filepath)
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)
    return FileResponse("static/scorepage.html")


# ── 外部 CSS（供評分報告 HTML 使用） ──
@app.get("/webhook/style.css")
async def serve_css():
    return FileResponse("style.css", media_type="text/css")
