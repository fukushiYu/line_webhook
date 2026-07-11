import base64
import random

import aiohttp

from config import GEMINI_API_KEYS, LLM_MODEL, GEMINI_PROMPT, GEMINI_AUDIO_PROMPT


async def _call_gemini(filepath: str, mime_type: str, prompt: str) -> str:
    api_key = random.choice(GEMINI_API_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={api_key}"

    with open(filepath, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": file_b64}},
            ]
        }]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return "無法辨識內容"


async def ocr_image(filepath: str) -> str:
    return await _call_gemini(filepath, "image/jpeg", GEMINI_PROMPT)


async def transcribe_audio(filepath: str, mime_type: str) -> str:
    return await _call_gemini(filepath, mime_type, GEMINI_AUDIO_PROMPT)
