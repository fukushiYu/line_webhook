import json
import asyncio

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import FileResponse

from linebot.v3.webhooks import MessageEvent, PostbackEvent

from config import CHANNEL_SECRET
from line_utils import verify_signature
from handlers import handle_message, handle_image_message, handle_audio_message, handle_postback

app = FastAPI()


@app.post("/webhook/line")
async def webhook(request: Request, x_line_signature: str = Header(None)):
    if x_line_signature is None:
        raise HTTPException(status_code=400, detail="Missing Signature")
    body = await request.body()
    if not verify_signature(CHANNEL_SECRET, body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    body_dict = json.loads(body.decode("utf-8"))
    for event_dict in body_dict.get("events", []):
        if event_dict.get("type") == "message":
            msg_type = event_dict.get("message", {}).get("type")
            if msg_type == "image":
                asyncio.create_task(handle_image_message(MessageEvent.from_dict(event_dict)))
            elif msg_type == "audio":
                asyncio.create_task(handle_audio_message(MessageEvent.from_dict(event_dict)))
            elif msg_type == "text":
                await handle_message(MessageEvent.from_dict(event_dict))
        elif event_dict.get("type") == "postback":
            await handle_postback(PostbackEvent.from_dict(event_dict))
    return "OK"


@app.get("/webhook/scorepage")
async def score_page():
    return FileResponse("static/scorepage.html")
