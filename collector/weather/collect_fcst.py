r"""기상청 단기예보·중기예보 수집기 (공공데이터포털, 2026-10-22)

단기예보  VilageFcstInfoService_2.0/getVilageFcst : 시군구 격자(nx,ny)마다 발표(02·05·08·11·14·17·20·23시)별 3일치 예보
중기예보  MidFcstInfoService/getMidLandFcst(육상 강수확률·날씨), getMidTa(최저·최고기온+범위), getMidFcst(전망 문장)
          발표 06·18시, 4~10일 뒤

- API는 최근 발표분만 줌 → 자주 돌려서 쌓아야 과거 예보가 남음 (서버: run.py collect --only fcst 를 3시간마다)
- 인증키: 환경변수 DATA_GO_KR_KEY 에서만 읽음(입력창 없음). 키는 파일에 저장 안 함
- 활용신청 필요(자동승인): 「기상청_단기예보 조회서비스」, 「기상청_중기예보 조회서비스」
- 주소는 ref/예보_설정.json(선택), 구역코드는 ref/중기구역.csv, 격자는 ref/시군구_좌표.csv
- 저장 폴더: --data 또는 환경변수 FCST_DIR (기본 data/raw/fcst)

사용
  python collect_fcst.py --probe              # 키·주소 확인 (격자 1개, 구역 1개만)
  python collect_fcst.py                      # 단기+중기, 아직 안 받은 최근 발표분
  python collect_fcst.py --part short --times all   # 단기: 최근 하루 8번 발표 전부 (기본은 최신 + 05·17시)
  python collect_fcst.py --export-only        # CSV·최신현황만 다시 만들기
출력 (data/raw/fcst/)
  01_단기예보_일별요약.csv   발표 × 시군구 × 예보일: 최저·최고(TMN/TMX, 없으면 TMP 최소·최대), 강수확률 최대, 강수량 합(mm), 적설 합(cm), 습도 평균, 풍속 최대
  02_중기예보_육상.csv       발표 × 육상구역 × n일 뒤(오전/오후): 강수확률·날씨
  03_중기예보_기온.csv       발표 × 도시 × n일 뒤: 최저·최고(+하한·상한 = 값 ∓ API의 Low/High 폭)
  04_중기전망_문장.csv       발표 × 지점: 전망 문장
  05_최신현황.json           단기·중기 가장 최근 발표시각과 예보가 덮는 마지막 날짜
  진행상태.sqlite3           받은 원본(JSON, 압축) — 이어받기
"""
import argparse, csv, datetime as dt, gzip, json, math, os, re, sqlite3, sys, time
import wxcommon  # urlopen 호출 수 세기 — urllib import보다 먼저
import urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = wxcommon.REF                   # 시군구_좌표.csv, 중기구역.csv 위치
OUT = Path(os.getenv('FCST_DIR') or (wxcommon.data_dir() / 'raw' / 'fcst'))   # 진행상태.sqlite3 + CSV
KST = dt.timezone(dt.timedelta(hours=9))
_G = wxcommon.DATA_GO_KR_BASE
CONF = {'단기_주소': _G + '/1360000/VilageFcstInfoService_2.0/getVilageFcst',
        '중기_육상_주소': _G + '/1360000/MidFcstInfoService/getMidLandFcst',
        '중기_기온_주소': _G + '/1360000/MidFcstInfoService/getMidTa',
        '중기_전망_주소': _G + '/1360000/MidFcstInfoService/getMidFcst',
        '중기_전망_지점': ['108'], '호출간격_초': 0.15}
if (HERE / '예보_설정.json').exists():
    CONF.update(json.loads((HERE / '예보_설정.json').read_text(encoding='utf-8-sig')))
SHORT_TIMES = ['0200', '0500', '0800', '1100', '1400', '1700', '2000', '2300']


class Stop(Exception):
    def __init__(self, msg, kind='auth'):   # kind: 'auth' | 'quota'
        super().__init__(msg); self.kind = kind
class Fail(Exception): pass


def now(): return dt.datetime.now(KST)


def call(url, params, key):
    q = {'serviceKey': key, 'dataType': 'JSON', **params}
    full = url + '?' + urllib.parse.urlencode(q, safe='%')
    for t in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers={'User-Agent': 'NongClock'}), timeout=40) as r:
                txt = r.read().decode('utf-8', 'replace')
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403): raise Stop(f'HTTP {e.code} (활용신청·인증키 확인)')
            if e.code == 429: raise Stop(f'HTTP {e.code} 호출 한도', 'quota')
            if t == 2: raise Fail(f'HTTP {e.code}')
        except Exception as e:
            if t == 2: raise Fail(type(e).__name__)
        time.sleep(2 * (t + 1))
    if txt.lstrip().startswith('<'):
        m = re.search(r'<returnAuthMsg>(.*?)</returnAuthMsg>|<resultMsg>(.*?)</resultMsg>', txt)
        msg = (m.group(1) or m.group(2)) if m else txt[:150]
        c = re.search(r'<returnReasonCode>(.*?)</returnReasonCode>', txt)
        kind = wxcommon.classify_go_kr(c.group(1) if c else '', msg)
        if kind: raise Stop(msg, kind)
        if 'KEY' in msg.upper(): raise Stop(msg)
        raise Fail(msg)
    js = json.loads(txt); h = js.get('response', {}).get('header', {})
    code, msg = str(h.get('resultCode', '')), h.get('resultMsg', '')
    if code == '03': return []                         # NO_DATA
    kind = wxcommon.classify_go_kr(code, msg)
    if kind: raise Stop(f'{code} {msg}', kind)
    if code not in ('00', ''): raise Fail(f'{code} {msg}')
    items = js['response']['body'].get('items') or {}
    it = items.get('item', []) if isinstance(items, dict) else []
    return [it] if isinstance(it, dict) else it


# ── 격자 변환 (기상청 LCC, 5km) ──
def latlon_to_grid(lat, lon):
    RE, GRID, SLAT1, SLAT2, OLON, OLAT, XO, YO = 6371.00877, 5.0, 30.0, 60.0, 126.0, 38.0, 43, 136
    D = math.pi / 180.0; re_ = RE / GRID; s1, s2, olon, olat = SLAT1 * D, SLAT2 * D, OLON * D, OLAT * D
    sn = math.log(math.cos(s1) / math.cos(s2)) / math.log(math.tan(math.pi * 0.25 + s2 * 0.5) / math.tan(math.pi * 0.25 + s1 * 0.5))
    sf = math.pow(math.tan(math.pi * 0.25 + s1 * 0.5), sn) * math.cos(s1) / sn
    ro = re_ * sf / math.pow(math.tan(math.pi * 0.25 + olat * 0.5), sn)
    ra = re_ * sf / math.pow(math.tan(math.pi * 0.25 + lat * D * 0.5), sn)
    th = lon * D - olon
    th = th - 2 * math.pi if th > math.pi else th + 2 * math.pi if th < -math.pi else th
    th *= sn
    return int(math.floor(ra * math.sin(th) + XO + 0.5)), int(math.floor(ro - ra * math.cos(th) + YO + 0.5))


def grids():
    g = {}
    with (HERE / '시군구_좌표.csv').open(encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            try: nx, ny = latlon_to_grid(float(r['위도']), float(r['경도']))
            except ValueError: continue
            g.setdefault((nx, ny), []).append(f"{r['시도']} {r['시군구']}")
    return g


def regions(kind):
    with (HERE / '중기구역.csv').open(encoding='utf-8-sig') as f:
        return [r for r in csv.DictReader(f) if r['종류'] == kind and r['코드'].strip()]


def db_open():
    db = sqlite3.connect(OUT / '진행상태.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS raw(kind TEXT, issue TEXT, point TEXT, n INTEGER, body BLOB, got TEXT, PRIMARY KEY(kind, issue, point))')
    return db


def have(db, kind, issue, point):
    return db.execute('SELECT 1 FROM raw WHERE kind=? AND issue=? AND point=?', (kind, issue, point)).fetchone() is not None


def put(db, kind, issue, point, rows):
    db.execute('INSERT OR REPLACE INTO raw VALUES(?,?,?,?,?,?)', (kind, issue, point, len(rows), gzip.compress(json.dumps(rows, ensure_ascii=False).encode()), now().isoformat(timespec='seconds')))


def short_issues(mode):
    t = now() - dt.timedelta(minutes=15)                # 발표 직후엔 아직 없을 수 있음(조회 가능 시각은 공식 문서에 없음). 없으면 저장 안 하고 다음 실행(24시간 안)에서 다시 받음
    cands = []
    for back in range(0, 2):
        d = (t - dt.timedelta(days=back)).date()
        for hm in SHORT_TIMES:
            ts = dt.datetime(d.year, d.month, d.day, int(hm[:2]), int(hm[2:]), tzinfo=KST)
            if ts <= t and t - ts < dt.timedelta(hours=24): cands.append(ts)
    cands.sort()
    if mode == 'all': return cands
    pick = {cands[-1]} if cands else set()
    pick |= {c for c in cands if c.strftime('%H%M') in ('0500', '1700')}
    return sorted(pick)


def mid_issues():
    t = now() - dt.timedelta(minutes=30); out = []
    for back in range(0, 2):
        d = (t - dt.timedelta(days=back)).date()
        for hh in (6, 18):
            ts = dt.datetime(d.year, d.month, d.day, hh, tzinfo=KST)
            if ts <= t and t - ts < dt.timedelta(hours=24): out.append(ts)
    return sorted(out)


def run_short(db, key, mode, probe):
    g = grids(); pts = list(g)[:1] if probe else list(g)
    iss = short_issues(mode)[-1:] if probe else short_issues(mode)
    print(f'[단기] 격자 {len(pts)}개 × 발표 {len(iss)}번: {", ".join(i.strftime("%m-%d %H시") for i in iss)}', flush=True)
    n = 0
    for ts in iss:
        bd, bt = ts.strftime('%Y%m%d'), ts.strftime('%H%M')
        todo = [p for p in pts if not have(db, 'short', bd + bt, f'{p[0]},{p[1]}')]
        for i, (nx, ny) in enumerate(todo, 1):
            try:
                rows = call(CONF['단기_주소'], {'pageNo': 1, 'numOfRows': 1500, 'base_date': bd, 'base_time': bt, 'nx': nx, 'ny': ny}, key)
            except Fail as e:
                print(f'  {bd} {bt} ({nx},{ny}) 실패 {e}', flush=True); FAILS[0] += 1; continue
            if not rows:   # 서버판 수정: 빈 응답(NO_DATA)은 저장하지 않음 → 다음 실행에서 다시 받음
                print(f'  {bd} {bt} ({nx},{ny}) 자료 없음(아직 미반영?) → 다음 실행에서 다시', flush=True); continue
            put(db, 'short', bd + bt, f'{nx},{ny}', rows); n += 1
            if i % 50 == 0: db.commit(); print(f'  {bd} {bt}: {i}/{len(todo)}', flush=True)
            if probe: print('  시험 응답', len(rows), '행, 예:', rows[:2], flush=True)
            time.sleep(CONF['호출간격_초'])
        db.commit()
    return n


def run_mid(db, key, probe):
    iss = mid_issues()[-1:] if probe else mid_issues()
    jobs = [('mid_land', CONF['중기_육상_주소'], r['코드']) for r in regions('육상')] + \
           [('mid_ta', CONF['중기_기온_주소'], r['코드']) for r in regions('기온')] + \
           [('mid_fcst', CONF['중기_전망_주소'], s) for s in CONF['중기_전망_지점']]
    if probe: jobs = [jobs[0], next(j for j in jobs if j[0] == 'mid_ta')]
    print(f'[중기] 발표 {len(iss)}번({", ".join(i.strftime("%m-%d %H시") for i in iss)}) × {len(jobs)}건', flush=True)
    n = 0
    for ts in iss:
        tm = ts.strftime('%Y%m%d%H%M')
        for kind, url, code in jobs:
            if have(db, kind, tm, code): continue
            p = {'pageNo': 1, 'numOfRows': 10, 'tmFc': tm, ('stnId' if kind == 'mid_fcst' else 'regId'): code}
            try: rows = call(url, p, key)
            except Fail as e: print(f'  {kind} {code} {tm} 실패 {e}', flush=True); FAILS[0] += 1; continue
            if not rows:   # 서버판 수정: 빈 응답은 저장하지 않음 → 24시간 안의 다음 실행에서 다시
                print(f'  {kind} {code} {tm} 자료 없음 → 다음 실행에서 다시', flush=True); continue
            put(db, kind, tm, code, rows); n += 1
            if probe: print(f'  시험 {kind} {code}:', json.dumps(rows[:1], ensure_ascii=False)[:400], flush=True)
            time.sleep(CONF['호출간격_초'])
        db.commit()
    return n


def num(v):
    try: return float(v)
    except (TypeError, ValueError):
        s = str(v)
        if '없음' in s or s.strip() in ('', '-'): return 0.0
        m = re.findall(r'[\d.]+', s)
        return float(m[-1]) if m else None      # '1mm 미만' → 1, '30.0~50.0mm' → 50


def export(db):
    out = OUT
    # 단기 일별요약
    names = grids(); rows_out = []; latest_s = None; last_day_s = None
    for issue, point, body in db.execute("SELECT issue, point, body FROM raw WHERE kind='short' ORDER BY issue"):
        rows = json.loads(gzip.decompress(body)); days = {}
        for r in rows:
            d = days.setdefault(r['fcstDate'], {})
            d.setdefault(r['category'], []).append(r['fcstValue'])
        nx, ny = map(int, point.split(','))
        for fd, c in sorted(days.items()):
            tmp = [num(x) for x in c.get('TMP', []) if num(x) is not None]
            rec = {'발표일시': f'{issue[:4]}-{issue[4:6]}-{issue[6:8]} {issue[8:10]}:{issue[10:12]}', 'nx': nx, 'ny': ny,
                   '시군구': ' | '.join(names.get((nx, ny), [])), '예보일': f'{fd[:4]}-{fd[4:6]}-{fd[6:]}',
                   '최저기온': num(c['TMN'][0]) if c.get('TMN') else (min(tmp) if tmp else ''),
                   '최고기온': num(c['TMX'][0]) if c.get('TMX') else (max(tmp) if tmp else ''),
                   '최저최고_근거': 'TMN/TMX' if c.get('TMN') or c.get('TMX') else ('시간별 TMP(그날 일부 시간만일 수 있음)' if tmp else ''),
                   '시간수': len(c.get('TMP', [])),
                   '강수확률_최대': max((num(x) or 0) for x in c.get('POP', ['0'])),
                   '강수량_합_mm': round(sum((num(x) or 0) for x in c.get('PCP', [])), 1),
                   '적설_합_cm': round(sum((num(x) or 0) for x in c.get('SNO', [])), 1),
                   '습도_평균': round(sum(num(x) or 0 for x in c.get('REH', [])) / max(1, len(c.get('REH', []))), 1) if c.get('REH') else '',
                   '풍속_최대': max((num(x) or 0) for x in c.get('WSD', ['0'])),
                   '이용가능시점': f'발표 후 약 10분 (API 반영)'}
            rows_out.append(rec); last_day_s = max(last_day_s or '', rec['예보일'])
        latest_s = max(latest_s or '', issue)
    F1 = ['발표일시', 'nx', 'ny', '시군구', '예보일', '최저기온', '최고기온', '최저최고_근거', '시간수', '강수확률_최대', '강수량_합_mm', '적설_합_cm', '습도_평균', '풍속_최대', '이용가능시점']
    with (out / '01_단기예보_일별요약.csv').open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, F1); w.writeheader(); w.writerows(rows_out)
    # 중기
    rnames = {r['코드']: r['이름'] for k in ('육상', '기온') for r in regions(k)}
    land, ta, txt = [], [], []; latest_m = None; last_day_m = None
    for kind, issue, point, body in db.execute("SELECT kind, issue, point, body FROM raw WHERE kind LIKE 'mid%' ORDER BY issue"):
        rows = json.loads(gzip.decompress(body))
        if not rows: continue
        r = rows[0]; base = dt.date(int(issue[:4]), int(issue[4:6]), int(issue[6:8]))
        latest_m = max(latest_m or '', issue); ts = f'{issue[:4]}-{issue[4:6]}-{issue[6:8]} {issue[8:10]}:00'
        if kind == 'mid_fcst':
            txt.append({'발표일시': ts, '지점': point, '전망': r.get('wfSv', '')}); continue
        by = {}
        for k, v in r.items():
            m = re.match(r'(rnSt|wf|taMin|taMax)(\d+)(Am|Pm|Low|High)?$', k)
            if m: by.setdefault(int(m.group(2)), {})[m.group(1) + (m.group(3) or '')] = v
        for nd, d in sorted(by.items()):
            day = str(base + dt.timedelta(days=nd)); last_day_m = max(last_day_m or '', day)
            if kind == 'mid_land':
                land.append({'발표일시': ts, '구역코드': point, '구역': rnames.get(point, ''), 'n일뒤': nd, '예보일': day,
                             '강수확률_오전': d.get('rnStAm', ''), '강수확률_오후': d.get('rnStPm', ''), '강수확률_하루': d.get('rnSt', ''),
                             '날씨_오전': d.get('wfAm', ''), '날씨_오후': d.get('wfPm', ''), '날씨_하루': d.get('wf', '')})
            else:
                # taMinLow/High는 '폭'(예: taMin4=13, Low=1, High=1 → 12~14℃). 2026-10-22 실제 응답으로 확인
                rng = lambda v, lo, hi: ('', '') if v in ('', None) else ((num(v) - num(lo)) if lo not in ('', None) else '', (num(v) + num(hi)) if hi not in ('', None) else '')
                a1, a2 = rng(d.get('taMin'), d.get('taMinLow'), d.get('taMinHigh')); b1, b2 = rng(d.get('taMax'), d.get('taMaxLow'), d.get('taMaxHigh'))
                ta.append({'발표일시': ts, '구역코드': point, '도시': rnames.get(point, ''), 'n일뒤': nd, '예보일': day,
                           '최저기온': d.get('taMin', ''), '최저_하한': a1, '최저_상한': a2,
                           '최고기온': d.get('taMax', ''), '최고_하한': b1, '최고_상한': b2,
                           '원자료_폭': f"최저 -{d.get('taMinLow', '')}/+{d.get('taMinHigh', '')}, 최고 -{d.get('taMaxLow', '')}/+{d.get('taMaxHigh', '')}"})
    for name, data in [('02_중기예보_육상.csv', land), ('03_중기예보_기온.csv', ta), ('04_중기전망_문장.csv', txt)]:
        with (out / name).open('w', newline='', encoding='utf-8-sig') as f:
            if data: w = csv.DictWriter(f, list(data[0].keys())); w.writeheader(); w.writerows(data)
    fmt = lambda s: f'{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}' if s else ''
    st = {'확인시각': now().isoformat(timespec='seconds'),
          '단기예보': {'최신발표': fmt(latest_s), '예보_마지막날': last_day_s, '발표수': db.execute("SELECT count(DISTINCT issue) FROM raw WHERE kind='short'").fetchone()[0],
                   '격자수': len(names), '일별요약행': len(rows_out)},
          '중기예보': {'최신발표': fmt(latest_m), '예보_마지막날': last_day_m, '육상행': len(land), '기온행': len(ta)}}
    (out / '05_최신현황.json').write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(st, ensure_ascii=False, indent=1), flush=True)


FAILS = [0]


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', choices=['all', 'short', 'mid'], default='all')
    ap.add_argument('--times', choices=['default', 'all'], default='default')
    ap.add_argument('--probe', action='store_true'); ap.add_argument('--export-only', action='store_true')
    ap.add_argument('--data', default=str(OUT), help='저장 폴더 (기본 data/raw/fcst)')
    a = ap.parse_args()
    OUT = Path(a.data); OUT.mkdir(parents=True, exist_ok=True); db = db_open()
    wxcommon.start()
    key = '' if a.export_only else wxcommon.get_key('DATA_GO_KR_KEY')
    if not a.export_only and not key:
        db.close(); wxcommon.exit_nokey('DATA_GO_KR_KEY')
    n_before = db.execute('SELECT count(*) FROM raw').fetchone()[0]
    try:
        if not a.export_only:
            if '%' in key: key = urllib.parse.unquote(key)   # Encoding 키를 넣었어도 동작
            if a.part in ('all', 'short'): run_short(db, key, a.times, a.probe)
            if a.part in ('all', 'mid'): run_mid(db, key, a.probe)
    except Stop as e:
        print('\n수집 중지:', e, '\n→ 공공데이터포털에서 「기상청_단기예보 조회서비스」·「기상청_중기예보 조회서비스」 활용신청 상태와 키를 확인하세요.', flush=True)
        db.commit(); export(db)
        wxcommon.STATS['added'] = db.execute('SELECT count(*) FROM raw').fetchone()[0] - n_before
        (wxcommon.exit_quota if e.kind == 'quota' else wxcommon.exit_auth)(e)
    except KeyboardInterrupt:
        print('중단. 받은 것은 보존됨', flush=True)
    finally:
        db.commit()
    # 추가 = 새로 저장한 원본 응답 수(발표 × 격자/구역 1건 = 1행)
    wxcommon.STATS['added'] = db.execute('SELECT count(*) FROM raw').fetchone()[0] - n_before
    if not a.probe: export(db)
    if FAILS[0]:
        wxcommon.error(f'예보 요청 {FAILS[0]}건 실패(다음 실행 때 남은 발표분 다시 시도)')
        sys.exit(wxcommon.EXIT_FAIL)


if __name__ == '__main__':
    main()
