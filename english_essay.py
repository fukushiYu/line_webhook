import re

# ── 判斷 OCR 結果是否為英文作文：檢查字數、句數、大寫開頭比例 ──
def is_english_essay(text: str) -> tuple[bool, str, str]:
    s = text.strip()
    if not s:
        return False, "文字內容為空白，無法判斷", s

    words = s.split()
    if len(words) < 30:  # 至少 30 個單字
        return False, f"字數不足（目前 {len(words)} 詞，需至少 30 詞）", s

    sentences = [x.strip() for x in re.split(r'[.!?]+', s) if x.strip()]
    if len(sentences) < 2:  # 至少 2 個句子
        return False, f"句子數量不足（目前 {len(sentences)} 句，需至少 2 句）", s

    upper_start = sum(1 for sen in sentences if sen and sen[0].isupper())  # 大寫開頭的句子數
    if len(sentences) == 0 or upper_start / len(sentences) < 0.5:  # 未達 50% 則不計
        return False, "大部分句子未以大寫開頭，不似英文作文格式", s

    return True, "", s
