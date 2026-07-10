import re

def is_english_essay(text: str) -> bool:
    # 先去掉前後空白
    s = text.strip()
    if not s:
        return False

    # 1. 排除有中文、日文、韓文、泰文等非英文語系
    has_cjk = re.search(r'[\u4e00-\u9fff\u3040-\u30ff\u3130-\u318f\u0e00-\u0e7f]', s)
    if has_cjk:
        return False

    # 2. 只允許：英文字母、標點、數字、空白
    allowed_pattern = re.compile(r'^[a-zA-Z0-9\s\.,!?\';:"\-()]+$')
    if not allowed_pattern.match(s):
        return False

    # 3. 字數至少 30 詞（太短不叫作文）
    words = s.split()
    if len(words) < 30:
        return False

    # 4. 至少 2 句以上
    sentences = [x.strip() for x in re.split(r'[.!?]+', s) if x.strip()]
    if len(sentences) < 2:
        return False

    # 5. 大部分句子開頭大寫（作文特徵）
    upper_start = sum(1 for sen in sentences if sen and sen[0].isupper())
    if len(sentences) == 0 or upper_start / len(sentences) < 0.5:
        return False

    # 全部通過 → 判定為英文作文
    return True

