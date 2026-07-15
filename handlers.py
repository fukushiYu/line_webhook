import uuid
import os

from linebot.v3.messaging import (
    AsyncApiClient,
    AsyncMessagingApi,
    AsyncMessagingApiBlob,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
)
from linebot.v3.webhooks import MessageEvent, PostbackEvent

from line_utils import configuration
from config import (
    FLEX_WELCOME,
    FLEX_UPLOAD,
    FLEX_GRADE,
    ADMIN,
    ADMIN_PREFIX,
    LIFF_URI,
    ENDPOINT_URL,
    RICH_MENU_A_ID,
)
from gemini import ocr_image, transcribe_audio, score_essay, md_to_html
from english_essay import is_english_essay


async def handle_message(event: MessageEvent):
    user_message = event.message.text.strip()
    source = event.source
    user_id = getattr(source, "user_id", "*")
    group_id = getattr(source, "group_id", "*")
    is_group = source.type == "group"

    if is_group:
        if user_message.startswith(ADMIN_PREFIX) and user_id == ADMIN:
            lower_text = user_message[len(ADMIN_PREFIX):].strip().lower()
        else:
             return
    else:
        lower_text = user_message.strip().lower()

    async with AsyncApiClient(configuration) as api_client:
        line_bot_api = AsyncMessagingApi(api_client)
        async def _reply(reply_token, message):
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]))
        if lower_text == "grade":
            flex_dict = FLEX_GRADE
            flex_dict["body"]["contents"][1]["action"]["uri"] = LIFF_URI
            await _reply(event.reply_token,FlexMessage(alt_text="評分", contents=FlexContainer.from_dict(flex_dict)),)
        elif lower_text == "welcome":
            await _reply(event.reply_token,FlexMessage(alt_text="歡迎", contents=FlexContainer.from_dict(FLEX_WELCOME)),)
        elif lower_text == "upload":
            await _reply( event.reply_token,FlexMessage(alt_text="上傳", contents=FlexContainer.from_dict(FLEX_UPLOAD)),)
        elif lower_text in ("menu", "選單"):
            await line_bot_api.link_rich_menu_id_to_user(user_id=user_id, rich_menu_id=RICH_MENU_A_ID)
            await _reply(event.reply_token, TextMessage(text="特殊圖文選單已為您開啟！"))
        else:
            echo = f"「{user_message}」\n（User ID 紀錄為：{user_id}）"
            echo += f"\n Group ID: {group_id}" if group_id != "*" else "\n---"
            await _reply(event.reply_token, TextMessage(text=echo))


async def handle_image_message(event: MessageEvent):
    source = event.source
    user_id = getattr(source, "user_id", "*")
    group_id = getattr(source, "group_id", "*")
    is_group = source.type == "group"
    message_id = event.message.id
    if is_group and user_id != ADMIN:
        return
    async with AsyncApiClient(configuration) as api_client:
        blob_api = AsyncMessagingApiBlob(api_client)
        content = await blob_api.get_message_content(message_id)
        basename = f"{uuid.uuid4()}"
        filename = basename + ".jpg"
        os.makedirs("images", exist_ok=True)
        filepath = os.path.join("images", filename)
        with open(filepath, "wb") as f:
            f.write(content)
        text = await ocr_image(filepath)
        ok, reason, cleaned = is_english_essay(text)
        if not ok:
            line_bot_api = AsyncMessagingApi(api_client)
            await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,messages=[TextMessage(text=f"這不是一篇英文作文：{reason}")],))
            return
        await score_essay(cleaned,basename) # create markdown
        await md_to_html(basename)          # markdown to html
        line_bot_api = AsyncMessagingApi(api_client)
        flex_dict = FLEX_GRADE
        flex_dict["body"]["contents"][1]["action"]["uri"] = f"{ENDPOINT_URL}?id={basename}"
        await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,messages=[FlexMessage(alt_text="評分結果", contents=FlexContainer.from_dict(flex_dict))],))

AUDIO_EXT_MAP = {
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/mpeg": ".mp3",
    "audio/amr": ".amr",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}


async def handle_audio_message(event: MessageEvent):
    source = event.source
    user_id = getattr(source, "user_id", "*")
    group_id = getattr(source, "group_id", "*")
    is_group = source.type == "group"
    message_id = event.message.id
    if is_group and user_id != ADMIN:
        return
    async with AsyncApiClient(configuration) as api_client:
        blob_api = AsyncMessagingApiBlob(api_client)
        resp = await blob_api.get_message_content_with_http_info(message_id)
        raw_data = resp.raw_data
        content_type = resp.headers.get("Content-Type", "audio/mp4")
        mime = content_type.split(";")[0].strip()
        ext = AUDIO_EXT_MAP.get(mime, ".m4a")
        filename = f"{uuid.uuid4()}{ext}"
        os.makedirs("audios", exist_ok=True)
        filepath = os.path.join("audios", filename)
        with open(filepath, "wb") as f:
            f.write(raw_data)
        text = await transcribe_audio(filepath, mime)
        line_bot_api = AsyncMessagingApi(api_client)
        await line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token,messages=[TextMessage(text=text)],))

async def handle_postback(event: PostbackEvent):
    pass
