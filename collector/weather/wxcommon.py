"""수집기 공통: 데이터 폴더, 인증키, 호출 수 세기, 종료 코드.

- 데이터 폴더: 환경변수 DATA_DIR (없으면 이 폴더의 ./data). 상대경로면 이 폴더 기준.
- 각 수집기는 끝날 때 한 줄을 출력함:  ##STATS {"calls": N, "added": M, "errors": [...]}
  run.py가 이 줄을 읽어 data/collect_log.json에 기록.
- 종료 코드: 0 정상 / 1 실패(다음 실행에서 다시 시도) / 2 인증키 없음
             3 인증 오류(키 미등록·만료·권한 없음) → run.py가 data/STOP_<키이름> 파일을 만듦
             4 호출 한도 초과(다음 날 다시 시도, STOP 파일 안 만듦)
"""
import atexit
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE / 'ref'

EXIT_FAIL, EXIT_NOKEY, EXIT_AUTH, EXIT_QUOTA = 1, 2, 3, 4

# 기본 주소 (시험할 때만 환경변수로 바꿈)
KMA_APIHUB_BASE = os.getenv('KMA_APIHUB_BASE', 'https://apihub.kma.go.kr').rstrip('/')
DATA_GO_KR_BASE = os.getenv('DATA_GO_KR_BASE', 'http://apis.data.go.kr').rstrip('/')

# 공공데이터포털 결과코드
GO_KR_AUTH_CODES = {'20', '30', '31', '32', '33'}   # 접근거부 / 미등록키 / 기한만료 / 미등록IP / 서명오류
GO_KR_QUOTA_CODES = {'22'}                         # 호출한도 초과
GO_KR_AUTH_WORDS = ('SERVICE_KEY', 'ACCESS_DENIED', 'ACCESS DENIED', 'DEADLINE', 'UNREGISTERED_IP', 'UNSIGNED_CALL')
GO_KR_QUOTA_WORDS = ('LIMITED_NUMBER', 'LIMITED NUMBER')


def data_dir():
    p = Path(os.getenv('DATA_DIR') or 'data')
    return (p if p.is_absolute() else HERE / p).resolve()


def get_key(name, aliases=()):
    """환경변수에서 키를 읽음. 없으면 '' (입력창 없음)."""
    for n in (name, *aliases):
        v = os.getenv(n, '').strip()
        if v:
            return v
    return ''


def classify_go_kr(code, msg):
    """공공데이터포털 결과코드·메시지 → 'auth' | 'quota' | None"""
    code = str(code or '').strip()
    up = str(msg or '').upper()
    if code.zfill(2) in GO_KR_QUOTA_CODES or any(w in up for w in GO_KR_QUOTA_WORDS):
        return 'quota'
    if code.zfill(2) in GO_KR_AUTH_CODES or any(w in up for w in GO_KR_AUTH_WORDS):
        return 'auth'
    return None


# ---------- 호출 수 세기 ----------
STATS = {'calls': 0, 'added': 0, 'errors': []}
_orig_urlopen = urllib.request.urlopen


def _counted_urlopen(*a, **k):
    STATS['calls'] += 1          # 실패한 요청(HTTP 오류·시간초과)도 1번으로 셈
    return _orig_urlopen(*a, **k)


# 이 모듈을 import하면 urllib.request.urlopen 호출이 모두 세어짐.
# (수집기에서 'from urllib.request import urlopen'보다 먼저 import해야 함)
urllib.request.urlopen = _counted_urlopen

_started = [False]


def start():
    """수집기 시작 시 1번 호출: 끝날 때 ##STATS 줄을 출력하게 함."""
    if not _started[0]:
        _started[0] = True
        atexit.register(_emit)


def _emit():
    STATS['errors'] = [str(e)[:300] for e in STATS['errors']][:50]
    print('##STATS ' + json.dumps(STATS, ensure_ascii=False), flush=True)


def error(msg):
    STATS['errors'].append(str(msg))


def exit_nokey(name):
    msg = f'인증키 없음: 환경변수 {name} 를 넣으세요(.env). 이 수집은 건너뜀'
    print('[오류] ' + msg, flush=True)
    error(msg)
    sys.exit(EXIT_NOKEY)


def exit_auth(reason):
    STATS['auth_error'] = str(reason)[:300]
    error('인증 오류: ' + str(reason))
    print(f'[중지] 인증 오류: {reason}', flush=True)
    sys.exit(EXIT_AUTH)


def exit_quota(reason):
    STATS['quota_error'] = str(reason)[:300]
    error('호출 한도: ' + str(reason))
    print(f'[중지] 호출 한도 초과: {reason} (다음 실행 때 다시 시도)', flush=True)
    sys.exit(EXIT_QUOTA)


def count_csv_rows(path):
    """CSV 데이터 행 수(헤더 제외). 파일 없으면 0. (따옴표 안 줄바꿈 없는 파일 기준)"""
    p = Path(path)
    if not p.exists():
        return 0
    with p.open('rb') as f:
        n = sum(1 for _ in f)
    return max(0, n - 1)
