import hashlib
import hmac
import base64

from linebot.v3.messaging import Configuration, AsyncApiClient, AsyncMessagingApi

from config import CHANNEL_ACCESS_TOKEN

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    expected = base64.b64encode(
        hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode()
    return hmac.compare_digest(signature, expected)


async def get_line_api() -> AsyncMessagingApi:
    client = AsyncApiClient(configuration)
    return AsyncMessagingApi(client)
