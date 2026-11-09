# -*- coding: utf-8 -*-
"""팜비드 일일 수집·DB 적재 공통 함수 (2026-11-06)
- 인증키: 환경변수 또는 이 폴더의 .env (키=값). 코드·로그에 키를 쓰지 않음
- 모든 시각은 한국 시간
"""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))
REF = HERE / 'ref'

KEY_NAMES = {
    'MAFRA_API_KEY': '농림축산식품 공공데이터포털(data.mafra.go.kr) 인증키 — 공영도매시장 정산가격',
    'KAMIS_KEY': 'KAMIS Open-API 인증키',
    'KAMIS_ID': 'KAMIS Open-API 요청자 ID',
    'KMA_APIHUB_KEY': '기상청 API허브(apihub.kma.go.kr) authKey — ASOS 일자료·기상특보',
    'DATA_GO_KR_KEY': '공공데이터포털(data.go.kr) 일반 인증키(Decoding) — 농업기상·단기·중기예보·특일·aT 출하예약',
    'SEOUL_OPENAPI_KEY': '서울 열린데이터광장(data.seoul.go.kr) 인증키 — 가락 경매전·후 반입물량',
    'ECOS_API_KEY': '한국은행 ECOS(ecos.bok.or.kr) 인증키 — 환율',
}


def now():
    return dt.datetime.now(KST)


def today():
    return now().date()


def load_env():
    f = HERE / '.env'
    if f.exists():
        for line in f.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# 데이터 폴더 (원장·표·기록). 코드는 git, 데이터는 git 밖에 두려고 FARMBID_DATA 로 위치를 바꿀 수 있다 (11-09)
# 환경변수나 이 폴더 .env 에 FARMBID_DATA=D:\nong-clock-data\05_DB적재\data  (없으면 이 폴더의 data)
load_env()
DATA = Path(os.getenv('FARMBID_DATA', HERE / 'data'))
RAW = Path(os.getenv('FARMBID_RAW', DATA / 'raw'))
OUT = Path(os.getenv('FARMBID_OUT', DATA / 'tables'))
LOG = DATA / 'log'


def key(name):
    load_env()
    v = os.getenv(name, '').strip()
    if not v:
        raise SystemExit(f'인증키 {name} 가 없습니다. .env 에 {name}=... 를 넣으세요 ({KEY_NAMES.get(name, "")})')
    return v


class ApiStop(Exception):
    """인증 오류·호출 한도: 이 자료 수집을 멈춤 (다음 실행 때 이어받기)"""


class ApiFail(Exception):
    """이 요청만 실패 (다음 실행 때 다시 시도)"""


def http_get(url, params=None, secret=(), timeout=60, tries=3, pause=1.0, raw=False):
    """GET 요청. secret 에 든 값(인증키)은 오류 문장에서 [KEY]로 가림."""
    full = url + ('?' + urllib.parse.urlencode(params, safe=':/') if params else '')
    hide = lambda s: _mask(str(s), secret)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(full, headers={'User-Agent': 'FarmBid-daily-collector/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            return body if raw else body.decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 429):
                raise ApiStop(f'HTTP {e.code}')
            last = f'HTTP {e.code}'
        except Exception as e:  # 연결 끊김 등
            last = type(e).__name__
        time.sleep(pause * (i + 1))
    raise ApiFail(hide(last))


def _mask(s, secret):
    for x in secret:
        if x:
            s = s.replace(x, '[KEY]').replace(urllib.parse.quote(x), '[KEY]')
    return s


def write_log(source, started, ok, rows_in=0, rows_saved=0, rows_rejected=0, api_calls=0, error='', note=''):
    """collect_log 테이블과 같은 모양으로 data/log/collect_log.csv 에 한 줄 추가"""
    LOG.mkdir(parents=True, exist_ok=True)
    f = LOG / 'collect_log.csv'
    new = not f.exists()
    import csv
    with f.open('a', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(['source', 'started_at', 'finished_at', 'ok', 'rows_in', 'rows_saved', 'rows_rejected', 'api_calls', 'error', 'note'])
        w.writerow([source, started.isoformat(timespec='seconds'), now().isoformat(timespec='seconds'), ok,
                    rows_in, rows_saved, rows_rejected, api_calls, error[:300], note[:300]])


def state(name):
    p = RAW / name / '_state.json'
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}


def save_state(name, st):
    p = RAW / name / '_state.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, p)


def days(start, end, newest_first=True):
    n = (end - start).days + 1
    out = [start + dt.timedelta(i) for i in range(n)]
    return out[::-1] if newest_first else out
