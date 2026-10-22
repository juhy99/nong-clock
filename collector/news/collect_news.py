"""농업 뉴스 수집기 (명세 docs/06_api_spec.md 2-14).

NAVER API HUB 뉴스 검색으로 기사를 받아 농업 기사만 골라 품목·분류 태그를 붙이고 data/news.json 에 쌓는다.
나중에 DB 가 생기면 save_news() 만 테이블 저장으로 바꾸면 된다.

  python collect_news.py            한 번 수집
  python collect_news.py --loop     1시간마다 계속 수집 (Ctrl+C 로 멈춤)
  python collect_news.py --relabel  저장된 기사에 바뀐 규칙을 다시 적용 (네이버 호출 없음)

키는 collector/news/.env 또는 환경변수 NAVER_CLIENT_ID · NAVER_CLIENT_SECRET (NAVER API HUB Application).
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import rules

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
NEWS_FILE = DATA / "news.json"            # 90일 전체 (DB 가 생기면 옮길 원본)
RECENT_FILE = DATA / "news-recent.json"   # 최근 7일 (화면이 읽는 파일. 전체는 수십 MB 가 되어 화면이 받기엔 큼)
LOG_FILE = DATA / "collect_log.json"
REJECTED_FILE = DATA / "rejected.json"

API_URL = os.environ.get("NAVER_NEWS_API_URL", "https://naverapihub.apigw.ntruss.com/search/v1/news")  # 바꿀 일은 거의 없음 (검사용 가짜 서버 등)
KST = timezone(timedelta(hours=9))
DISPLAY = 100          # 한 번에 받는 기사 수 (최대 100)
MAX_START = 1000       # 네이버 검색은 start 1000 까지만
KEEP_DAYS = 90         # 보관 기간
RECENT_DAYS = 7        # 화면용 파일 기간 ("이번 주 많이 나온 품목"이 7일)
INTERVAL_MIN = 60      # --loop 간격
CALL_GAP_SEC = 0.15    # 호출 사이 쉬는 시간 (키당 초당 50회 제한보다 넉넉히)
LOG_KEEP = 100         # 수집 기록 보관 개수
OVERLAP = timedelta(hours=2)  # 네이버에 늦게 올라오는 기사를 놓치지 않게 지난 수집보다 2시간 앞부터 다시 본다 (중복은 주소로 거름)


def now():
    return datetime.now(KST)


def load_env():
    """collector/news/.env 의 KEY=VALUE 를 환경변수로 (이미 있는 값은 그대로)"""
    env = HERE / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, data):
    """임시 파일에 쓴 뒤 바꿔 끼운다 (쓰다가 멈춰도 기존 파일이 깨지지 않게)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def search(query, start=1):
    """뉴스 검색 한 번. 실패하면 RuntimeError (메시지에 네이버 오류 문구)"""
    params = urllib.parse.urlencode({"query": query, "display": DISPLAY, "start": start, "sort": "date"})
    req = urllib.request.Request(f"{API_URL}?{params}", headers={
        "X-NCP-APIGW-API-KEY-ID": os.environ.get("NAVER_CLIENT_ID", "").strip(),
        "X-NCP-APIGW-API-KEY": os.environ.get("NAVER_CLIENT_SECRET", "").strip(),
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body).get("error", {})
            msg = f"{err.get('message')} ({err.get('details')})"
        except (ValueError, AttributeError):
            msg = body[:200]
        raise RuntimeError(f"HTTP {e.code}: {msg}") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"연결 실패: {e}") from None
    if not isinstance(data.get("items"), list):
        raise RuntimeError(f"응답 형식이 다릅니다: {str(data)[:200]}")
    return data["items"]


def fetch_query(query, since):
    """검색어 하나의 새 기사. 최신순으로 받다가 since(마지막 성공 시각 - 2시간)보다 오래된 기사가 나오면 멈춘다.
    처음 수집(since 없음)이면 첫 페이지만."""
    out = []
    start = 1
    while start <= MAX_START:
        items = search(query, start)
        time.sleep(CALL_GAP_SEC)
        for a in items:
            if since and parsedate_to_datetime(a["pubDate"]) <= since:
                return out
            out.append(a)
        if not since or len(items) < DISPLAY:
            return out
        start += DISPLAY
    return out


def label(a):
    """네이버 기사 → 저장 모양. 농업 기사가 아니면 None"""
    url = a.get("originallink") or a.get("link")
    title = rules.clean(a.get("title"))
    summary = rules.clean(a.get("description"))
    published = parsedate_to_datetime(a["pubDate"]).astimezone(KST)
    return {
        "id": hashlib.sha1(url.encode("utf-8")).hexdigest()[:12],
        "title": title,
        "summary": summary,
        "press": rules.press_of(url),
        "url": url,
        "published_at": published.isoformat(),
        "items": rules.find_items(f"{title} {summary}"),
        "crops": rules.find_crops(f"{title} {summary}"),
        "category": rules.categorize(title, summary),
        "score": rules.agri_score(title, summary),
    }


def save_news(articles, updated_at):
    """기사 저장 (지금은 JSON 파일. DB 가 생기면 여기만 바꾼다)"""
    articles.sort(key=lambda n: n["published_at"], reverse=True)
    recent_limit = (updated_at - timedelta(days=RECENT_DAYS)).isoformat()
    for path, rows in ((NEWS_FILE, articles), (RECENT_FILE, [n for n in articles if n["published_at"] >= recent_limit])):
        write_json(path, {
            "updated_at": updated_at.isoformat(),
            "next_update_at": (updated_at + timedelta(minutes=INTERVAL_MIN)).isoformat(),
            "count": len(rows),
            "articles": rows,
        })


def drop_old(articles, at):
    limit = (at - timedelta(days=KEEP_DAYS)).isoformat()
    return [n for n in articles if n["published_at"] >= limit]


def collect():
    """한 번 수집. 반환: 수집 기록 한 줄"""
    started = now()
    log = read_json(LOG_FILE, {"last_success_at": None, "runs": []})
    since = datetime.fromisoformat(log["last_success_at"]) - OVERLAP if log.get("last_success_at") else None
    stored = read_json(NEWS_FILE, {"articles": []})["articles"]
    seen = {n["url"] for n in stored} | {rules.title_key(n["title"]) for n in stored}

    raw, errors = [], []
    queries = rules.queries()
    for q in queries:
        try:
            raw += fetch_query(q, since)
        except RuntimeError as e:
            errors.append(f"{q}: {e}")
            print(f"  ✗ {q}: {e}", file=sys.stderr)
            if str(e).startswith(("HTTP 401", "HTTP 403")):  # 키 문제면 나머지 검색어도 똑같이 실패하므로 멈춤
                break

    added, rejected = [], []
    for a in sorted(raw, key=lambda a: parsedate_to_datetime(a["pubDate"]), reverse=True):
        url = a.get("originallink") or a.get("link")
        key = rules.title_key(rules.clean(a.get("title")))
        if not url or url in seen or key in seen:
            continue
        seen |= {url, key}
        n = label(a)
        if rules.is_agri_news(n["title"], n["summary"]):
            added.append(n | {"collected_at": started.isoformat()})
        else:
            rejected.append({k: n[k] for k in ("title", "summary", "url", "score", "items", "crops")})

    ok = bool(raw) or not errors  # 받은 기사가 하나도 없고 오류만 있으면 실패 (기존 기사는 그대로)
    finished = now()
    run = {
        "started_at": started.isoformat(), "finished_at": finished.isoformat(), "ok": ok,
        "queries": len(queries), "received": len(raw), "added": len(added), "rejected": len(rejected), "errors": errors,
    }
    if ok:
        save_news(drop_old(stored + added, finished), finished)
        write_json(REJECTED_FILE, {"collected_at": finished.isoformat(), "articles": rejected})
        # 다음 수집은 이번 시작 시각(- 2시간) 이후 기사부터
        log["last_success_at"] = started.isoformat()
    log["runs"] = ([run] + log.get("runs", []))[:LOG_KEEP]
    write_json(LOG_FILE, log)
    return run


def relabel():
    """저장된 기사에 바뀐 규칙을 다시 적용 (태그 다시 붙이고 농업 기사가 아니게 된 것은 뺀다)"""
    data = read_json(NEWS_FILE, None)
    if not data:
        print("저장된 기사가 없습니다. 먼저 수집하세요.")
        return
    kept, dropped = [], 0
    for n in data["articles"]:
        if not rules.is_agri_news(n["title"], n["summary"]):
            dropped += 1
            continue
        text = f"{n['title']} {n['summary']}"
        kept.append(n | {
            "items": rules.find_items(text), "crops": rules.find_crops(text),
            "category": rules.categorize(n["title"], n["summary"]), "score": rules.agri_score(n["title"], n["summary"]),
        })
    save_news(kept, datetime.fromisoformat(data["updated_at"]))
    print(f"다시 적용: {len(kept)}건 남김, {dropped}건 뺌")


def print_run(r):
    mark = "✓" if r["ok"] else "✗"
    print(f"{mark} {r['finished_at'][:16]}  검색어 {r['queries']}개 · 받은 기사 {r['received']} · 새로 저장 {r['added']} · 거름 {r['rejected']}"
          + (f" · 실패 {len(r['errors'])}" if r["errors"] else ""))


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔·파일로 돌릴 때 한글·기호가 깨져 멈추지 않게
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="팜비드 농업 뉴스 수집기")
    p.add_argument("--loop", action="store_true", help=f"{INTERVAL_MIN}분마다 계속 수집")
    p.add_argument("--relabel", action="store_true", help="저장된 기사에 규칙 다시 적용 (네이버 호출 없음)")
    args = p.parse_args()

    if args.relabel:
        relabel()
        return
    load_env()
    if not os.environ.get("NAVER_CLIENT_ID") or not os.environ.get("NAVER_CLIENT_SECRET"):
        sys.exit("NAVER_CLIENT_ID · NAVER_CLIENT_SECRET 이 없습니다. collector/news/.env 를 만들어 주세요 (.env.example 참고)")
    while True:
        r = collect()
        print_run(r)
        if not args.loop:
            sys.exit(0 if r["ok"] else 1)
        time.sleep(INTERVAL_MIN * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n멈춤")
