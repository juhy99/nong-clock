"""농업기상 관측데이터 수집기 (농촌진흥청 국립농업과학원, 공공데이터포털 data.go.kr)

  서비스: 농업기상 기본 관측데이터 조회 (https://www.data.go.kr/data/15078057/openapi.do)
  주소  : http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/V2/GnrlWeather/getWeatherMonDayList
  요청  : serviceKey, Page_No, Page_Size, search_Year, search_Month (+ 선택 obsr_Spot_Code)
  -> 월 단위로 전 관측지점의 일별 자료를 받음. 응답 항목은 이름 그대로 전부 저장.

- 원래 파일: agri_weather.py (리눅스 서버용으로 경로·키 읽기만 바꿈)
- 표준 라이브러리만 사용. 인증키는 환경변수 DATA_GO_KR_KEY 에서만 읽음 (입력창 없음)
- 서버판 수정: 끝난 달은 '그 달 말일 + 2일 이후에 받은 적이 있을 때'만 완료로 봄
  (예전에는 지난달 마지막 날 자료가 빠진 채 완료로 남을 수 있었음)
- 인증키는 '일반 인증키(Decoding)' 권장. Encoding 키를 넣어도 자동 처리.
- 월별 작업은 끝까지(totalCount) 받으면 완료 처리 -> 다시 실행하면 남은 달만 받음.
- 서비스 주소/오퍼레이션이 바뀌면 --url, --op 로 바꿔 실행.
"""
from __future__ import annotations
import argparse, calendar, csv, datetime as dt, json, os, pathlib, sqlite3, sys, time
import wxcommon  # urlopen 호출 수 세기 — urllib import보다 먼저
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

URL = wxcommon.DATA_GO_KR_BASE + '/1390802/AgriWeather/WeatherObsrInfo/V2/GnrlWeather'
CONF = {}
_cf = wxcommon.REF / '농업기상_설정.txt'
if _cf.exists():                     # 포털 주소가 바뀌면 이 파일만 고치면 됨 (서비스URL=..., 오퍼레이션=...)
    for _l in _cf.read_text(encoding='utf-8-sig').splitlines():
        if '=' in _l and not _l.strip().startswith('#'):
            _k, _v = _l.split('=', 1); CONF[_k.strip()] = _v.strip()
    URL = CONF.get('서비스URL', URL).rstrip('/')
    if os.getenv('DATA_GO_KR_BASE'):   # 시험용: 주소 앞부분만 바꿈
        URL = URL.replace('http://apis.data.go.kr', wxcommon.DATA_GO_KR_BASE)
URL = os.getenv('AGRI_URL', URL).rstrip('/')
STOP_CODES = {'12', '20', '22', '30', '31', '32', '33'}   # 서비스없음/접근거부/호출한도초과/미등록키/기한만료/IP/서명오류
NODATA_CODES = {'03'}

class Stop(Exception):
    def __init__(self, msg, kind=None):   # kind: 'auth' | 'quota' | None
        super().__init__(msg); self.kind = kind
class Fail(Exception): pass

def keyparam(key):
    return key if '%' in key else urllib.parse.quote(key, safe='')

def call(key, op, params, timeout=90):
    url = f'{URL}/{op}?serviceKey={keyparam(key)}&' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'NongClock student research'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: raw = r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')[:300].replace(key, '[KEY]').replace(keyparam(key), '[KEY]')
        if e.code in (401, 403): raise Stop(f'HTTP {e.code} {body}', 'auth')
        if e.code == 429: raise Stop(f'HTTP {e.code} {body}', 'quota')
        raise Fail(f'HTTP {e.code} {body}')
    except Exception as e:
        raise Fail(type(e).__name__)
    txt = raw.decode('utf-8', errors='replace').strip()
    if txt.startswith('{'):                                    # JSON으로 오는 경우
        js = json.loads(txt); resp = js.get('response', js)
        head, body = resp.get('header', {}), resp.get('body', {})
        code, msg = str(head.get('resultCode', head.get('result_Code', ''))), str(head.get('resultMsg', head.get('result_Msg', '')))
        items = (body.get('items') or {}).get('item', []) if isinstance(body.get('items'), dict) else (body.get('items') or [])
        if isinstance(items, dict): items = [items]
        total = int(body.get('totalCount', body.get('total_Count', len(items))) or 0)
    else:
        try: root = ET.fromstring(txt)
        except ET.ParseError: raise Fail('XML/JSON 아님: ' + txt[:150].replace(key, '[KEY]'))
        g = lambda tag: (root.findtext(f'.//{tag}') or '').strip()
        code = g('resultCode') or g('result_Code') or g('returnReasonCode')
        msg = g('resultMsg') or g('result_Msg') or g('returnAuthMsg') or g('errMsg')
        items = [{c.tag: (c.text or '').strip() for c in it if c.tag != 'no'} for it in root.iter('item')]
        total = int(g('totalCount') or g('total_Count') or len(items))
    if code in NODATA_CODES or 'NODATA' in msg.upper(): return 0, [], 'no_data'
    kind = wxcommon.classify_go_kr(code, msg)
    if kind: raise Stop(f'{code} {msg}', kind)
    if code and code not in ('00', '0', '200', 'INFO-000') :
        if code.zfill(2) in STOP_CODES or any(w in msg.upper() for w in ('SERVICE_KEY', 'LIMITED', 'ACCESS DENIED', 'DEADLINE')):
            raise Stop(f'{code} {msg}')
        raise Fail(f'{code} {msg}')
    return total, items, 'ok'

def fetch_month(key, op, ym, size, spot, delay):
    y, m = ym[:4], ym[4:]
    base = {'Page_Size': size, 'search_Year': y, 'search_Month': m, **({'obsr_Spot_Code': spot} if spot else {})}
    total, items, st = call(key, op, {'Page_No': 1, **base}); time.sleep(delay)
    if st == 'no_data' or (total == 0 and not items): return [], 0
    allitems, page = list(items), 1
    while len(allitems) < total:
        page += 1
        t2, more, _ = call(key, op, {'Page_No': page, **base}); time.sleep(delay)
        if not more: raise Fail(f'{page}쪽이 비어 있음 ({len(allitems)}/{total})')
        allitems += more
        if page > 5000: raise Fail('페이지 수 비정상')
    return allitems, total


_B = 'http://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo'
_M = {'Page_No': 1, 'Page_Size': 5, 'search_Year': '2024', 'search_Month': '05'}
PROBES = [   # (설명, 기본주소, 오퍼레이션, 요청변수)  — 2025-11 개편: 오퍼레이션 이름 끝에 3
    ('설정파일 주소', URL, CONF.get('오퍼레이션', 'getWeatherMonDayList3'), _M),
    ('V3 월별', _B + '/V3/GnrlWeather', 'getWeatherMonDayList3', _M),
    ('V2 월별3', _B + '/V2/GnrlWeather', 'getWeatherMonDayList3', _M),
    ('GnrlWeather 월별3', _B + '/GnrlWeather', 'getWeatherMonDayList3', _M),
    ('V3 경로없음 월별3', _B + '/V3', 'getWeatherMonDayList3', _M),
    ('WeatherObsrInfo 바로 월별3', _B, 'getWeatherMonDayList3', _M),
    ('V3 GnrlWeather3', _B + '/V3/GnrlWeather3', 'getWeatherMonDayList3', _M),
]

def probe(key):
    print('여러 요청 형식을 차례로 시험합니다. 결과 화면을 그대로 캡처해서 보내주세요.\n')
    for name, base, op, params in PROBES:
        url = f'{base}/{op}?serviceKey={keyparam(key)}&' + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'NongClock'}), timeout=60) as r:
                st, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            st, body = e.code, e.read()
        except Exception as e:
            st, body = type(e).__name__, b''
        txt = body.decode('utf-8', errors='replace').replace(key, '[KEY]').replace(keyparam(key), '[KEY]')
        print(f'== {name}: HTTP {st}\n   {" ".join(txt.split())[:500]}\n')

def db_open(out):
    db = sqlite3.connect(out / '진행상태.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS jobs(ym TEXT PRIMARY KEY, status TEXT, total INTEGER, error TEXT, updated TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS rows(ym TEXT, n INTEGER, payload TEXT, PRIMARY KEY(ym, n))')
    return db

def save(db, ym, status, rows=None, total=0, error=''):
    with db:
        if rows is not None:
            db.execute('DELETE FROM rows WHERE ym=?', (ym,))
            db.executemany('INSERT INTO rows VALUES(?,?,?)', [(ym, i, json.dumps(r, ensure_ascii=False)) for i, r in enumerate(rows)])
        db.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?,?,?)', (ym, status, total, error, dt.datetime.now().isoformat(timespec='seconds')))

def export(db, out):
    (out / '월별CSV').mkdir(exist_ok=True)
    keys, n = [], 0
    yms = [r[0] for r in db.execute('SELECT DISTINCT ym FROM rows ORDER BY 1')]
    for ym in yms:
        for (p,) in db.execute('SELECT payload FROM rows WHERE ym=? LIMIT 50', (ym,)):
            for k in json.loads(p):
                if k not in keys: keys.append(k)
    with (out / '농업기상_일자료_통합.csv').open('w', newline='', encoding='utf-8-sig') as fa:
        wa = csv.writer(fa); wa.writerow(['수집연월'] + keys)
        for ym in yms:
            recs = [json.loads(p) for (p,) in db.execute('SELECT payload FROM rows WHERE ym=? ORDER BY n', (ym,))]
            with (out / '월별CSV' / f'{ym}.csv').open('w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f); w.writerow(['수집연월'] + keys)
                for r in recs:
                    row = [ym] + [r.get(k, '') for k in keys]; w.writerow(row); wa.writerow(row)
            n += len(recs)
    # 지점 목록: 이름에 spot/stn/obsr 가 들어간 열로 중복 제거
    sk = [k for k in keys if any(s in k.lower() for s in ('spot', 'stn', 'obsr', 'addr', 'lat', 'lon', 'alt'))]
    if sk:
        seen = {}
        for (p,) in db.execute('SELECT payload FROM rows'):
            r = json.loads(p); t = tuple(r.get(k, '') for k in sk); seen[t] = seen.get(t, 0) + 1
        with (out / '관측지점_목록.csv').open('w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f); w.writerow(sk + ['행수']); [w.writerow(list(t) + [c]) for t, c in sorted(seen.items())]
    st = list(db.execute('SELECT * FROM jobs ORDER BY ym'))
    with (out / '수집진행현황.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(['연월', '상태', '행수', '오류', '처리시각']); w.writerows(st)
    cnt = {}
    for s in st: cnt[s[1]] = cnt.get(s[1], 0) + 1
    summary = {'자료': '농진청 농업기상 일별 관측', '행수': n, '열': keys, '작업상태': cnt,
               '주의': '열 이름은 API 원래 이름. 결측코드·단위는 공공데이터포털 명세서로 확인. failed는 다시 실행하면 재시도.'}
    (out / '수집요약.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != '열'}, ensure_ascii=False), '\n열:', ', '.join(keys))

def month_closed(ym, updated):
    """그 달 말일 + 2일 이후에 받은 기록이면 True (그 전이면 다시 받음)"""
    try:
        y, m = int(ym[:4]), int(ym[4:6])
        last = dt.date(y, m, calendar.monthrange(y, m)[1])
        return dt.date.fromisoformat(str(updated)[:10]) >= last + dt.timedelta(days=2)
    except (ValueError, TypeError):
        return False

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--start', default='2015-01'); ap.add_argument('--end', default=dt.date.today().strftime('%Y-%m'))
    ap.add_argument('--op', default=CONF.get('오퍼레이션', 'getWeatherMonDayList3')); ap.add_argument('--size', type=int, default=1000)
    ap.add_argument('--spot', default='', help='관측지점코드 (비우면 전체)'); ap.add_argument('--delay', type=float, default=0.3)
    ap.add_argument('--test', action='store_true'); ap.add_argument('--probe', action='store_true'); ap.add_argument('--export-only', action='store_true')
    ap.add_argument('--out', default=str(wxcommon.data_dir() / 'raw' / 'agri'), help='결과 폴더 (기본 data/raw/agri)')
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True); db = db_open(out)
    wxcommon.start()
    rows_before = db.execute('SELECT count(*) FROM rows').fetchone()[0]
    exit_code, stop = 0, None
    key = wxcommon.get_key('DATA_GO_KR_KEY')
    if not key and not a.export_only:
        db.close(); wxcommon.exit_nokey('DATA_GO_KR_KEY')
    try:
        if a.export_only: return
        if a.probe: probe(key); return
        if a.test:
            total, items, st = call(key, a.op, {'Page_No': 1, 'Page_Size': 5, 'search_Year': '2024', 'search_Month': '05', **({'obsr_Spot_Code': a.spot} if a.spot else {})})
            print(f'[시험] 2024-05: 상태 {st}, 전체 {total}행 (한 달 x 전 지점이면 수천~수만 행이어야 정상)')
            for it in items[:3]: print('   ', it)
            print('시험 끝. 행이 보이면 run.py collect --only agri 실행.'); return
        s, e = dt.date.fromisoformat(a.start + '-01'), dt.date.fromisoformat(a.end + '-01')
        yms, d = [], e
        while d >= s:
            yms.append(d.strftime('%Y%m')); d = (d.replace(day=1) - dt.timedelta(1)).replace(day=1)
        this_month = dt.date.today().strftime('%Y%m')
        done = {ym for ym, upd in db.execute("SELECT ym, updated FROM jobs WHERE status IN ('ok','no_data')")
                if month_closed(ym, upd)} - {this_month}   # 이번 달·막 끝난 달은 매번 새로 받음
        todo = [ym for ym in yms if ym not in done]
        print(f'대상 {len(yms)}개월, 남은 {len(todo)}개월 (최신부터)')
        for i, ym in enumerate(todo, 1):
            try:
                rows, total = fetch_month(key, a.op, ym, a.size, a.spot, a.delay)
                save(db, ym, 'ok' if rows else 'no_data', rows, total)
                print(f'[{i}/{len(todo)}] {ym}: ' + (f'{len(rows)}행' if rows else '자료없음'), flush=True)
            except Fail as ex:
                save(db, ym, 'failed', error=str(ex)); print(f'[{i}/{len(todo)}] {ym}: 실패 {ex}', flush=True)
                wxcommon.error(f'농업기상 {ym}: {ex}'); exit_code = wxcommon.EXIT_FAIL
    except KeyboardInterrupt:
        print('\n중단. 받은 달은 보존됩니다. 다시 실행하면 이어받기.')
        exit_code = wxcommon.EXIT_FAIL
    except Stop as ex:
        print(f'\n수집 중지: {ex}\n활용신청 승인 여부(승인 후 1~2시간 뒤 사용 가능)나 하루 호출한도를 확인하세요.', flush=True)
        stop = ex
    finally:
        if not (a.test or a.probe): export(db, out)
        wxcommon.STATS['added'] = db.execute('SELECT count(*) FROM rows').fetchone()[0] - rows_before   # DB 행 수 증가분
        db.close()
    if stop is not None:
        if stop.kind == 'auth': wxcommon.exit_auth(stop)
        if stop.kind == 'quota': wxcommon.exit_quota(stop)
        wxcommon.error(f'농업기상 중지: {stop}'); sys.exit(wxcommon.EXIT_FAIL)
    if exit_code: sys.exit(exit_code)

if __name__ == '__main__':
    main()
