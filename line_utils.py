import hashlib
import hmac
import base64

from linebot.v3.messaging import Configuration, AsyncApiClient, AsyncMessagingApi


# ── LINE Webhook HMAC-SHA256 簽章驗證 ──
def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    expected = base64.b64encode(
        hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(signature, expected)


# ── 根據 channel_config 建立 LINE API 客戶端（工具函式） ──
async def get_line_api(channel_config: dict) -> AsyncMessagingApi:
    config = Configuration(access_token=channel_config["channel_access_token"])
    client = AsyncApiClient(config)
    return AsyncMessagingApi(client)
