import hashlib
import hmac
import base64
import json
import uuid
import os
import random
import asyncio
import aiohttp

import yaml
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import FileResponse

from linebot.v3.messaging import (Configuration, AsyncApiClient, AsyncMessagingApi, AsyncMessagingApiBlob, ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, AudioMessageContent, PostbackEvent

app = FastAPI()

with open("settings.yaml", "r", encoding="utf-8") as f:
    conf = yaml.safe_load(f)

CHANNEL_SECRET = conf["channel_secret"]
CHANNEL_ACCESS_TOKEN = conf["channel_access_token"]
FLEX_WELCOME = conf["flex_welcome"]
FLEX_UPLOAD  = conf["flex_upload"]
FLEX_GRADE   = conf["flex_grade"]
ADMIN        = conf['admin']
ADMIN_PREFIX = conf['admin_prefix']
LIFF_URI     = conf['liff_uri']

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
RICH_MENU_A_ID = "richmenu-xxxxxxxxxxxxxx"


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    expected = base64.b64encode(hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()).decode()
    return hmac.compare_digest(signature, expected)


# --------------------------------------------------------------------------
@app.post("/webhook/line")
async def api(request: Request, x_line_signature: str = Header(None)):
    if x_line_signature is None:
        raise HTTPException(status_code=400, detail="Missing Signature")
    body = await request.body()
    if not verify_signature(CHANNEL_SECRET, body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
    body_dict = json.loads(body.decode("utf-8"))
    events = body_dict.get("events", [])
    for event_dict in events:
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


# *** 展現 LIFF 的網頁
@app.get("/webhook/scorepage")
async def score_page():
    return FileResponse("static/scorepage.html")


# *** 處理文字訊息
async def handle_message(event: MessageEvent):	
    user_message = event.message.text.strip()
    source = event.source
    user_id = getattr(source, 'user_id', "*")
    group_id = getattr(source, 'group_id', "*")
    source_type = source.type
    is_group = source_type == 'group'
    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)

        async def _reply(reply_token, message):
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]),)

        if is_group:
            if user_message.startswith(ADMIN_PREFIX) and user_id==ADMIN:
                lower_text = user_message[len(ADMIN_PREFIX):].strip().lower()
            else:
                return
        else:
            lower_text = user_message.strip().lower()

        if lower_text in ["grade"]:
            flex_dict = FLEX_GRADE
            flex_dict["body"]["contents"][1]["action"]["uri"] = LIFF_URI
            await _reply(event.reply_token, FlexMessage(alt_text="評分", contents=FlexContainer.from_dict(flex_dict)))
        elif lower_text in ["welcome"]:
            await _reply(event.reply_token, FlexMessage(alt_text="歡迎", contents=FlexContainer.from_dict(FLEX_WELCOME)))
        elif lower_text in ["upload"]:
            await _reply(event.reply_token, FlexMessage(alt_text="上傳", contents=FlexContainer.from_dict(FLEX_UPLOAD)))
        elif lower_text in ["menu", "選單"]:
            await line_bot_api.link_rich_menu_id_to_user(user_id=user_id, rich_menu_id=RICH_MENU_A_ID)
            await _reply(event.reply_token, TextMessage(text="特殊圖文選單已為您開啟！"))
        else:
            echo_text = f"「{user_message}」\n（User ID 紀錄為：{user_id}）"
            echo_text += f"\n Group ID: {group_id}" if group_id != "*" else "\n---"
            # echo_text =json.dumps(event.to_dict(),ensure_ascii=False,indent=3)
            await _reply(event.reply_token, TextMessage(text=echo_text))


# *** 處理圖片訊息
async def handle_image_message(event: MessageEvent):
    message_id = event.message.id
    async with AsyncApiClient(configuration) as api_client:
        line_bot_blob_api = AsyncMessagingApiBlob(api_client)
        content = await line_bot_blob_api.get_message_content(message_id)
        filename = f"{uuid.uuid4()}.jpg"
        os.makedirs("images", exist_ok=True)
        filepath = os.path.join("images", filename)
        with open(filepath, "wb") as f:
            f.write(content)

        # OCR via Gemini
        api_key = random.choice(conf["gemini_api_key"])
        model = conf["llm_model"]
        prompt = conf["gemini_prompt"]

        with open(filepath, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}}
                ]
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()

        try:
            ocr_text = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            ocr_text = "無法辨識圖片內容"

        line_bot_api = AsyncMessagingApi(api_client)
        await line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=ocr_text)]
            )
        )


# *** 處理音訊訊息
async def handle_audio_message(event: MessageEvent):
    message_id = event.message.id
    async with AsyncApiClient(configuration) as api_client:
        line_bot_blob_api = AsyncMessagingApiBlob(api_client)
        resp = await line_bot_blob_api.get_message_content_with_http_info(message_id)
        data = resp.raw_data
        headers = resp.headers
        content_type = headers.get("Content-Type", "audio/mp4")
        ext_map = {
            "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/mpeg": ".mp3",
            "audio/amr": ".amr", "audio/wav": ".wav", "audio/webm": ".webm",
            "audio/ogg": ".ogg",
        }
        ext = ext_map.get(content_type.split(";")[0].strip(), ".m4a")
        filename = f"{uuid.uuid4()}{ext}"
        os.makedirs("audios", exist_ok=True)
        filepath = os.path.join("audios", filename)
        with open(filepath, "wb") as f:
            f.write(data)

        # Transcription via Gemini
        api_key = random.choice(conf["gemini_api_key"])
        model = conf["llm_model"]
        prompt = conf["gemini_audio_prompt"]

        with open(filepath, "rb") as f:
            audio_base64 = base64.b64encode(f.read()).decode()

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": content_type.split(";")[0].strip(), "data": audio_base64}}
                ]
            }]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                result = await resp.json()

        try:
            transcript = result["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            transcript = "無法辨識音訊內容"

        line_bot_api = AsyncMessagingApi(api_client)
        await line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=transcript)]
            )
        )


# *** 處理POSTBACK文字訊息
async def handle_postback(event: PostbackEvent):
    pass
