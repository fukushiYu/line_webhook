import hashlib
import hmac
import base64
import json

import yaml
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import FileResponse

from linebot.v3.messaging import (Configuration, AsyncApiClient, AsyncMessagingApi, ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, PostbackEvent

app = FastAPI()

with open("settings.yaml", "r", encoding="utf-8") as f:
    conf = yaml.safe_load(f)

CHANNEL_SECRET = conf["channel_secret"]
CHANNEL_ACCESS_TOKEN = conf["channel_access_token"]
FLEX_WELCOME = conf["flex_welcome"]
FLEX_UPLOAD  = conf["flex_upload"]
FLEX_GRADE   = conf["flex_grade"]
ADMIN        = conf['admin']

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

LIFF_URL = "https://liff.line.me/1655962952-sRG07EcN"
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
            if msg_type == "text":
                await handle_message(MessageEvent.from_dict(event_dict))
            elif msg_type == "image":
                await handle_image_message(MessageEvent.from_dict(event_dict))
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
    lower_text = user_message.lower()
    #user_id = event.source.user_id
    source = event.source
    user_id = getattr(source, 'user_id', "*")
    group_id = getattr(source, 'group_id', "*")
    source_type = source.type
    is_group = source_type == 'group'
    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)

        async def _reply(reply_token, message):
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]),)

        if lower_text in ["grade"]:
            flex_dict = FLEX_GRADE
            flex_dict["body"]["contents"][1]["action"]["uri"] = LIFF_URL
            await _reply(event.reply_token, FlexMessage(alt_text="你好", contents=FlexContainer.from_dict(flex_dict)))
        elif lower_text in ["welcome"]:
            await _reply(event.reply_token, FlexMessage(alt_text="你好", contents=FlexContainer.from_dict(FLEX_WELCOME)))
        elif lower_text in ["upload"]:
            await _reply(event.reply_token, FlexMessage(alt_text="你好", contents=FlexContainer.from_dict(FLEX_UPLOAD)))
        elif lower_text in ["menu", "選單"]:
            await line_bot_api.link_rich_menu_id_to_user(user_id=user_id, rich_menu_id=RICH_MENU_A_ID)
            await _reply(event.reply_token, TextMessage(text="特殊圖文選單已為您開啟！"))
        elif user_id == ADMIN and user_message.startswith("@小英"):
            echo_text = f"「{user_message}」\n（User ID 紀錄為：{user_id}）"
            echo_text += f"\n Group ID: {group_id}" if group_id != "*" else "\n---"
            # echo_text =json.dumps(event.to_dict(),ensure_ascii=False,indent=3)
            await _reply(event.reply_token, TextMessage(text=echo_text))


# *** 處理圖片訊息
async def handle_image_message(event: MessageEvent):
    message_id = event.message.id


# *** 處理POSTBACK文字訊息
async def handle_postback(event: PostbackEvent):
    pass
