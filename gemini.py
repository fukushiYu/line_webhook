import base64,os
import random
import re
import aiohttp
import config

# ── 通用 Gemini API 呼叫（多媒體內容：圖片/音訊 → base64 內嵌） ──
async def _call_gemini(filepath: str, mime_type: str, prompt: str) -> str:
    api_key = random.choice(config.GEMINI_API_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.LLM_MODEL}:generateContent?key={api_key}"

    with open(filepath, "rb") as f:
        file_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": file_b64}},
            ]
        }],
        "generationConfig": {"maxOutputTokens": config.MAX_OUTPUT_TOKENS}
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()

    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return "無法辨識內容"


# ── 圖片 OCR ──
async def ocr_image(filepath: str) -> str:
    return await _call_gemini(filepath, "image/jpeg", config.GEMINI_OCR_PROMPT)

# ── 語音轉寫 ──
async def transcribe_audio(filepath: str, mime_type: str) -> str:
    return await _call_gemini(filepath, mime_type, config.GEMINI_AUDIO_PROMPT)

# ── 純文字 Gemini API 呼叫（評分用，結果存為 .md） ──
async def _call_gemini_text(prompt: str, text: str, file_id: str) -> str:
    api_key = random.choice(config.GEMINI_API_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.LLM_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"parts": [
                {"text": prompt},
                {"text": f"學生的文章：\n{text}"},]}],
        "generationConfig": {"maxOutputTokens": config.MAX_OUTPUT_TOKENS}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
    try:
        result_text = result["candidates"][0]["content"]["parts"][0]["text"]
        os.makedirs("output", exist_ok=True)
        with open(os.path.join("output", f"{file_id}.md"), "w", encoding="utf-8") as f:
            f.write(result_text)
    except (KeyError, IndexError):
        return "無法評分"

# ── 英文作文評分（使用 elementary_prompt） ──
async def score_essay(text: str, file_id: str) -> str:
    return await _call_gemini_text(config.ELEMENTARY_PROMPT, text, file_id)

# ── 英文作文評分（使用 elementary_prompt_html，直出 HTML，不經 .md） ──
# V2 模式：合併 scoring + md_to_html 為一次 Gemini 呼叫。
# 原 V1 流程需 3 次呼叫（OCR → scoring → md_to_html），V2 降為 2 次（OCR → scoring 直出 HTML）。
# elementary_prompt_html.txt 將評分規約與 HTML 輸出格式合併為單一 prompt，
# 使 Gemini 直接輸出與原本 md_to_html 相同的 HTML 結構，確保 LIFF 頁面完全相容。
async def score_essay_direct_html(text: str, file_id: str) -> str:
    api_key = random.choice(config.GEMINI_API_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.LLM_MODEL}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"parts": [
                {"text": config.ELEMENTARY_HTML_PROMPT},
                {"text": f"學生的文章：\n{text}"},
            ]}
        ],
        "generationConfig": {"maxOutputTokens": config.MAX_OUTPUT_TOKENS}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
    try:
        result_text = result["candidates"][0]["content"]["parts"][0]["text"]
        html = _inject_logo(_extract_html(result_text), config.LOGO_URL)
        os.makedirs("output", exist_ok=True)
        with open(os.path.join("output", f"{file_id}.html"), "w", encoding="utf-8") as f:
            f.write(html)
    except (KeyError, IndexError):
        return "<p>無法評分</p>"

# ── 英文作文評分（V3 模式）：單次 Gemini 呼叫，直接讀圖完成 OCR + 評分 + HTML ──
# V3 模式：將 OCR、scoring、md_to_html 三者合併為一次 Gemini 呼叫。
# 以 _call_gemini 將圖片 base64 內嵌，使用 elementary_prompt_html_direct.txt
# （OCR 指示 + 評分規約 + HTML 輸出格式），回覆經 _extract_html 清理與 _inject_logo
# 注入後直接寫入 output/{file_id}.html。非英文作文由模型依提示詞輸出固定回退 HTML。
async def score_essay_from_image(filepath: str, file_id: str) -> str:
    raw = await _call_gemini(filepath, "image/jpeg", config.ELEMENTARY_HTML_DIRECT_PROMPT)
    if raw == "無法辨識內容":
        return "<p>無法評分</p>"
    html = _inject_logo(_extract_html(raw), config.LOGO_URL)
    os.makedirs("output", exist_ok=True)
    with open(os.path.join("output", f"{file_id}.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return html

# ── 從 Gemini 回覆中擷取第一組 DOCTYPE / html 標籤，移除 markdown 圍欄 ──
def _extract_html(raw: str) -> str:
    for marker in ("<!DOCTYPE", "<!doctype", "<html"):
        pos = raw.find(marker)
        if pos != -1:
            raw = raw[pos:]
            break
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    return raw

# ── 於 <article> 開頭注入可設定的 Logo（<img class="score-logo">，高度由 style.css 控制） ──
# logo_url 為空字串時不注入，維持原 HTML。找不到 <article> 退而插入 <body> 之後，再找不到則插在最前端。
def _inject_logo(html: str, logo_url: str) -> str:
    if not logo_url:
        return html
    img_tag = f'<img class="score-logo" src="{logo_url}" alt="logo">'
    for pattern in (r"<article[^>]*>", r"<body[^>]*>"):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            pos = match.end()
            return html[:pos] + "\n" + img_tag + html[pos:]
    return img_tag + "\n" + html

# ── 將評分結果 .md 轉換為卡片式 HTML 頁面 ──
async def md_to_html(file_id: str) -> str:
    api_key = random.choice(config.GEMINI_API_KEYS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.LLM_MODEL}:generateContent?key={api_key}"
    with open(os.path.join("output",f"{file_id}.md"), 'r', encoding='utf-8') as f:
        md_text = f.read()
    payload = {"contents": [{"parts": [{"text": config.MD_TO_HTML_PROMPT},{"text": md_text},]}], "generationConfig": {"maxOutputTokens": config.MAX_OUTPUT_TOKENS}}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
    html = _inject_logo(_extract_html(result["candidates"][0]["content"]["parts"][0]["text"]), config.LOGO_URL)
    try:
        os.makedirs("output", exist_ok=True)
        with open(os.path.join("output", f"{file_id}.html"), "w", encoding="utf-8") as f:
            f.write(html)
    except (KeyError, IndexError):
        return "<p>轉換失敗</p>"
