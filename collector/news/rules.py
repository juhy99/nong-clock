"""농업 뉴스 거르기·품목 태그 규칙.

단어 목록과 기준 점수는 shared/news_rules.json 에 있고, 화면(frontend/src/utils/itemMatch.js,
frontend/src/mocks/news.js)도 같은 파일을 읽는다. 찾는 방식(아래 함수)을 바꾸면 JS 쪽도 똑같이 바꿔야 한다.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

RULES_PATH = Path(__file__).resolve().parents[2] / "shared" / "news_rules.json"
RULES = json.loads(RULES_PATH.read_text(encoding="utf-8"))

ITEM_WORDS = RULES["items"]
OTHER_CROPS = RULES["other_crops"]
NOT_ITEM = RULES["not_item"]
MISREAD = {code: re.compile(p) for code, p in RULES["misread"].items()}
AFTER_SINGLE = RULES["single_char"]["after"]
COUNT_BEFORE = re.compile(RULES["single_char"]["count_before"])
HANGUL = re.compile("[가-힣]")
SCORE = RULES["score"]
CATEGORIES = RULES["categories"]
PRESS = RULES["press"]


def _matcher(w):
    return re.compile(w["re"]) if isinstance(w, dict) else w


AGRI_WORDS = [_matcher(w) for w in RULES["agri_words"]]
NOISE_WORDS = [_matcher(w) for w in RULES["noise_words"]]
CONTEXT_WORDS = [_matcher(w) for w in RULES["context_words"]]


def _by_length(entries):
    """긴 이름부터 찾아야 '양배추' 안의 '배추', '배추' 안의 '배'를 잘못 세지 않는다"""
    words = [(code, w) for code, ws in entries for w in ws]
    return sorted(words, key=lambda cw: -len(cw[1]))  # 안정 정렬: 길이가 같으면 규칙 파일 순서 (JS 와 같음)


WORDS = _by_length(ITEM_WORDS.items())
CROP_WORDS = _by_length((code, c["words"]) for code, c in OTHER_CROPS.items())


def _ok_boundary(text, start, w):
    """한 글자 품목(배·무·귤)은 앞에 한글이 없고, 뒤에 한글이 없거나 조사·'값' 같은 짧은 말이 올 때만 품목"""
    if len(w) > 1:
        return True
    if COUNT_BEFORE.search(text[max(0, start - 8):start]):
        return False
    before = text[start - 1] if start > 0 else ""
    after = text[start + 1] if start + 1 < len(text) else ""
    if before and HANGUL.match(before):
        return False
    return not after or not HANGUL.match(after) or after in AFTER_SINGLE


def _match_codes(text, words):
    t = str(text or "")
    for n in NOT_ITEM:
        t = t.replace(n, " " * len(n))
    taken = [False] * len(t)
    hits = []
    for code, w in words:
        i = t.find(w)
        while i != -1:
            if not any(taken[i:i + len(w)]) and _ok_boundary(t, i, w):
                for k in range(i, i + len(w)):
                    taken[k] = True
                hits.append((i, code))
            i = t.find(w, i + 1)
    out = []
    for _, code in sorted(hits, key=lambda h: h[0]):
        if code not in out:
            out.append(code)
    return out


def find_items(text):
    """글에 나온 16개 품목 코드 (나온 순서대로, 중복 없이)"""
    text = str(text or "")
    return [c for c in _match_codes(text, WORDS) if not (c in MISREAD and MISREAD[c].search(text))]


def find_crops(text):
    """16개 품목 밖 작물 코드 (예: '샤인머스캣 수출' → ['grape'])"""
    return _match_codes(text, CROP_WORDS)


def _has(text, w):
    return w in text if isinstance(w, str) else bool(w.search(text))


def agri_score(title, summary):
    def score(words, t, s):
        return sum(t if _has(title, w) else s if _has(summary, w) else 0 for w in words)

    return score(AGRI_WORDS, SCORE["agri_title"], SCORE["agri_summary"]) - score(
        NOISE_WORDS, SCORE["noise_title"], SCORE["noise_summary"])


def is_agri_news(title, summary=""):
    s = agri_score(title, summary)
    crop_in_title = bool(find_items(title) or find_crops(title))
    topic_in_title = crop_in_title or any(_has(title, w) for w in AGRI_WORDS + CONTEXT_WORDS)
    if s >= SCORE["keep"] or (s >= SCORE["keep_with_topic"] and topic_in_title):
        return True
    text = f"{title} {summary}"
    return crop_in_title and s >= SCORE["keep_crop_in_title"] and any(_has(text, w) for w in CONTEXT_WORDS + AGRI_WORDS)


def categorize(title, summary):
    """분류별 단어가 제목에 나오면 2점, 요약에 나오면 1점. 점수가 가장 높은 분류, 없으면 '기타'"""
    best, best_score = "기타", 0
    for cat, words in CATEGORIES.items():
        score = sum((2 if w in title else 0) + (1 if w in summary else 0) for w in words)
        if score > best_score:
            best, best_score = cat, score
    return best


ENTITIES = {"&quot;": '"', "&amp;": "&", "&lt;": "<", "&gt;": ">", "&apos;": "'", "&#39;": "'", "&nbsp;": " "}


def clean(s):
    """네이버 응답의 <b> 태그·&quot; 같은 HTML 을 지운다 (화면 테스트 모드와 같은 글자만)"""
    t = re.sub(r"<[^>]+>", "", str(s or ""))
    t = re.sub(r"&[a-zA-Z#0-9]+;", lambda m: ENTITIES.get(m.group(0), m.group(0)), t)
    return re.sub(r"^[\s\ufeff]+|[\s\ufeff]+$", "", t)  # JS trim() 처럼 BOM 까지 지움


def press_of(url):
    try:
        host = re.sub(r"^(www|m|news|n)\.", "", urlparse(url).hostname or "")
    except ValueError:
        return ""
    for domain, name in PRESS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host


def title_key(title):
    """같은 보도자료를 여러 언론사가 그대로 싣는 경우: 띄어쓰기·기호를 뺀 제목이 같으면 같은 기사"""
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", title)


def queries():
    """검색어: 기본 + 품목 16개 + 품목 밖 작물 (화면 테스트 모드와 같음)"""
    q = list(RULES["queries"]["base"])
    if RULES["queries"].get("add_items"):
        q += [ws[0] for ws in ITEM_WORDS.values()]
    if RULES["queries"].get("add_other_crops"):
        q += [c["name"] for c in OTHER_CROPS.values()]
    return q
