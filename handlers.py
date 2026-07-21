import uuid
import os
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from linebot.v3.messaging import (
    Configuration,
    AsyncApiClient,
    AsyncMessagingApi,
    AsyncMessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
)
from linebot.v3.webhooks import MessageEvent, PostbackEvent

from config import (
    FLEX_WELCOME,
    FLEX_UPLOAD,
    FLEX_GRADE,
    FLEX_WAIT,
)
from gemini import ocr_image, transcribe_audio, score_essay, md_to_html
from english_essay import is_english_essay

TAIPEI_TZ = ZoneInfo("Asia/Taipei")
DAILY_IMAGE_LIMIT = 10

_processing_users: set[str] = set()
_state_lock = asyncio.Lock()

_user_daily_usage: dict[str, dict] = {}
_usage_lock = asyncio.Lock()

def _make_api(channel_config: dict) -> AsyncMessagingApi:
    return AsyncMessagingApi(AsyncApiClient(Configuration(access_token=channel_config["channel_access_token"])))

async def handle_message(event: MessageEvent, channel_config: dict):
    user_message = event.message.text.strip()
    source = event.source
    user_id = getattr(source, "user_id", "*")
    group_id = getattr(source, "group_id", "*")
    is_group = source.type == "group"

    admin = channel_config["admin"]
    admin_prefix = channel_config["admin_prefix"]

    if is_group:
        if user_message.startswith(admin_prefix) and user_id == admin:
            lower_text = user_message[len(admin_prefix):].strip().lower()
        else:
             return
    else:
        lower_text = user_message.strip().lower()

    line_bot_api = _make_api(channel_config)
    async def _reply(reply_token, message):
        await line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[message]))
    if lower_text == "grade":
        flex_dict = FLEX_GRADE
        flex_dict["body"]["contents"][1]["action"]["uri"] = channel_config["liff_uri"]
        await _reply(event.reply_token,FlexMessage(alt_text="評分", contents=FlexContainer.from_dict(flex_dict)),)
    elif lower_text == "welcome":
        await _reply(event.reply_token,FlexMessage(alt_text="歡迎", contents=FlexContainer.from_dict(FLEX_WELCOME)),)
    elif lower_text == "upload":
        await _reply( event.reply_token,FlexMessage(alt_text="上傳", contents=FlexContainer.from_dict(FLEX_UPLOAD)),)
    elif lower_text in ("menu", "選單"):
        await line_bot_api.link_rich_menu_id_to_user(user_id=user_id, rich_menu_id=channel_config["rich_menu_id"])
        await _reply(event.reply_token, TextMessage(text="特殊圖文選單已為您開啟！"))
    else:
        echo = f"「{user_message}」\n（User ID 紀錄為：{user_id}）"
        echo += f"\n Group ID: {group_id}" if group_id != "*" else "\n---"
        await _reply(event.reply_token, TextMessage(text=echo))


async def handle_image_message(event: MessageEvent, channel_config: dict):
    source = event.source
    user_id = getattr(source, "user_id", "*")
    group_id = getattr(source, "group_id", "*")
    is_group = source.type == "group"
    message_id = event.message.id

    if is_group and user_id != channel_config["admin"]:
        return

    # ── 重覆處理檢查 ──
    async with _state_lock:
        if user_id in _processing_users:
            busy = True
        else:
            busy = False
            _processing_users.add(user_id)

    if busy:
        line_bot_api = _make_api(channel_config)
        await line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="您有圖片正在處理中，請稍候再上傳。")],
            )
        )
        return

    try:
        # ── 每日用量檢查 ──
        async with _usage_lock:
            today = datetime.now(TAIPEI_TZ).date()
            record = _user_daily_usage.get(user_id)
            if record and record["date"] == today:
                if record["count"] >= DAILY_IMAGE_LIMIT:
                    line_bot_api = _make_api(channel_config)
                    await line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="您今天已達每日使用上限，請明天再來。")],
                        )
                    )
                    return
                record["count"] += 1
            else:
                _user_daily_usage[user_id] = {"date": today, "count": 1}

        # ── 正式處理 ──
        api_client = AsyncApiClient(Configuration(access_token=channel_config["channel_access_token"]))
        line_bot_api = AsyncMessagingApi(api_client)
        await line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text="請稍候", contents=FlexContainer.from_dict(FLEX_WAIT))],
            )
        )
        blob_api = AsyncMessagingApiBlob(api_client)
        content = await blob_api.get_message_content(message_id)
        basename = f"{uuid.uuid4()}"
        filename = basename + ".jpg"
        os.makedirs("images", exist_ok=True)
        filepath = os.path.join("images", filename)
        with open(filepath, "wb") as f:
            f.write(content)
        await api_client.close()

        text = await ocr_image(filepath)
        ok, reason, cleaned = is_english_essay(text)
        if not ok:
            line_bot_api = _make_api(channel_config)
            await line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=f"這不是一篇英文作文：{reason}")],
                )
            )
            return

        await score_essay(cleaned, basename)
        await md_to_html(basename)
        flex_dict = FLEX_GRADE
        flex_dict["body"]["contents"][1]["action"]["uri"] = f"{channel_config['endpoint_url']}?id={basename}"
        line_bot_api = _make_api(channel_config)
        await line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[FlexMessage(alt_text="評分結果", contents=FlexContainer.from_dict(flex_dict))],
            )
        )
    finally:
        async with _state_lock:
            _processing_users.discard(user_id)

AUDIO_EXT_MAP = {
    "audio/mp4": ".m4a",
    "audio/aac": ".aac",
    "audio/mpeg": ".mp3",
    "audio/amr": ".amr",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}


async def handle_audio_message(event: MessageEvent, channel_config: dict):
    source = event.source
    user_id = getattr(source, "user_id", "*")
    group_id = getattr(source, "group_id", "*")
    is_group = source.type == "group"
    message_id = event.message.id
    if is_group and user_id != channel_config["admin"]:
        return
    api_client = AsyncApiClient(Configuration(access_token=channel_config["channel_access_token"]))
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
    await api_client.close()

async def handle_postback(event: PostbackEvent, channel_config: dict):
    pass
