# -*- coding: utf-8 -*-
"""팜비드 일일 수집기 (2026-11-06) — DB 테이블 설계안 기준으로 매일 들어오는 자료만 받는다.

  python collect.py test                 # 인증키·연결 시험 (자료마다 1건)
  python collect.py daily                # 매일 실행: 아래 6개를 차례로 (빠진 날은 알아서 이어받기)
  python collect.py auction --start 2026-10-01 --end 2026-11-05   # 하나만, 기간 지정(과거 채우기)
  자료: auction(공영도매 정산가격) kamis(KAMIS 도·소매) warning(기상특보) holiday(특일)
        sanji(산지공판장) garak_inout(가락 경매전·후 반입) at_resv(aT 출하예약) fx(환율) policy(정부 수급정책)
        weather(ASOS·AWS·농업기상·장기전망 + 통합 전처리) fcst(단기·중기예보, 3시간마다) ← 이 둘은 팀 날씨 수집기(weather/)
  python collect.py fcst                 # 예보만 (3시간마다 따로 돌림: 5_예보_3시간마다_등록.bat / cron)

결과: data/raw/<자료>/  (원본 그대로에 가깝게, 날짜·달마다 파일 하나). 표로 바꾸기는 build_tables.py
기록: data/log/collect_log.csv  (collect_log 테이블과 같은 모양)
"""
import argparse
import csv
import datetime as dt
import gzip
import io
import json
import math
import sys
import xml.etree.ElementTree as ET

import common as C
from common import ApiFail, ApiStop

YDAY = lambda: C.today() - dt.timedelta(1)


def d8(d):
    return d.strftime('%Y%m%d')


def read_csv(path):
    with path.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


# ───────────────────────── 1. 공영도매시장 정산가격 (농식품부, 시장·품목·품종·등급·산지 건별) ─────────────────────────
MAFRA_BASE = 'http://211.237.50.150:7080/openapi'
MAFRA_GRID = 'Grid_20240625000000000653_1'
AUCTION_KOR = {
    'SALEDATE': '정산일자', 'WHSALCD': '도매시장코드', 'WHSALNAME': '도매시장명', 'CMPCD': '법인_공판장코드', 'CMPNAME': '법인_공판장명',
    'LARGE': '대분류코드', 'LARGENAME': '대분류명', 'MID': '중분류코드', 'MIDNAME': '중분류명', 'SMALL': '소분류코드', 'SMALLNAME': '소분류명',
    'DANQ': '단위중량', 'DANCD': '단위코드', 'POJCD': '포장코드', 'STD': '규격', 'SIZECD': '크기코드', 'SIZENAME': '크기명',
    'LVCD': '등급코드', 'LVNAME': '등급명', 'SANCD': '산지코드', 'SANNAME': '산지명', 'TOTQTY': '총물량', 'TOTAMT': '총금액',
    'MINAMT': '최저가', 'MAXAMT': '최고가', 'AVGAMT': '평균가'}
PRIVATE = {'CHULNAME', 'FARMNAME'}  # 출하자·생산자 이름은 저장하지 않음


def mafra_call(k, start, end, params, grid=None):
    grid = grid or MAFRA_GRID
    import urllib.parse
    url = f'{MAFRA_BASE}/{urllib.parse.quote(k)}/json/{grid}/{start}/{end}'
    txt = C.http_get(url, params, secret=(k,), timeout=90)
    try:
        js = json.loads(txt)
    except json.JSONDecodeError:
        raise ApiFail('JSON 아님')
    body = js.get(grid, js)
    res = body.get('result', {}) if isinstance(body, dict) else {}
    code, msg = str(res.get('code', '')), str(res.get('message', ''))
    if code == 'INFO-200':
        return 0, []
    if code and code != 'INFO-000':
        if code in ('INFO-100', 'INFO-300', 'ERROR-300', 'ERROR-301', 'ERROR-310', 'ERROR-350') or any(w in msg for w in ('인증', '트래픽', '한도', '초과', '권한')):
            raise ApiStop(f'{code} {msg}')
        raise ApiFail(f'{code} {msg}')
    rows = body.get('row', []) or []
    rows = [rows] if isinstance(rows, dict) else rows
    return int(body.get('totalCnt', len(rows)) or 0), rows


def auction(start, end, recheck=7):
    """날짜 × 시장마다 받음. 최근 recheck 일 안의 '자료없음'은 다시 확인 (월요일 자료가 화요일에 올라오는 등)"""
    k = C.key('MAFRA_API_KEY')
    mk = [r['market_code'] for r in read_csv(C.REF / 'market.csv') if r['is_active'] == 'True' and r['market_code'] != 'national']
    st = C.state('auction')
    out = C.RAW / 'auction'
    out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    cut = d8(C.today() - dt.timedelta(recheck))
    for d in C.days(start, end):
        ds = d8(d)
        done = st.get(ds, {})
        todo = [m for m in mk if done.get(m) != 'ok' and not (done.get(m) == 'no_data' and ds < cut)]
        if not todo:
            continue
        rows_day = []
        f = out / f'{ds}.csv.gz'
        if f.exists():  # 이미 받은 시장 행은 살림
            with gzip.open(f, 'rt', encoding='utf-8-sig') as fh:
                rows_day = [r for r in csv.DictReader(fh) if r['도매시장코드'] not in todo]
        for m in todo:
            try:
                total, rows = mafra_call(k, 1, 1000, {'SALEDATE': ds, 'WHSALCD': m}); calls += 1
                s = 1001
                while len(rows) < total:
                    _, more = mafra_call(k, s, s + 999, {'SALEDATE': ds, 'WHSALCD': m}); calls += 1
                    if not more:
                        raise ApiFail('빈 페이지')
                    rows += more; s += 1000
                for r in rows:
                    rows_day.append({AUCTION_KOR[c]: r.get(c, '') for c in AUCTION_KOR})
                done[m] = 'ok' if rows else 'no_data'
            except ApiFail as e:
                done[m] = 'failed'
                print(f'  {ds} {m} 실패: {e}', flush=True)
        st[ds] = done
        with gzip.open(f, 'wt', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(AUCTION_KOR.values()))
            w.writeheader(); w.writerows(rows_day)
        C.save_state('auction', st)
        saved += len(rows_day)
        print(f'  공영도매 {ds}: {len(rows_day):,}행 (시장 ok {sum(v == "ok" for v in done.values())}/{len(mk)})', flush=True)
    return calls, saved


# ───────────────────────── 2. KAMIS 일별 부류별 도·소매 가격 ─────────────────────────
KAMIS_URL = 'https://www.kamis.or.kr/service/price/xml.do'
KAMIS_FIELDS = ['조회일자', '가격구분', '부류코드', '품목코드', '품목명', '품종코드', '품종명', '등급코드', '등급', '단위', '가격']


def kamis(start, end):
    """휴일에는 KAMIS가 앞 조사일 값을 돌려줌 → day1 이 요청일과 다르면 버림. 아침에는 '-'가 많아 최근 21일을 다시 받음"""
    kk, kid = C.key('KAMIS_KEY'), C.key('KAMIS_ID')
    out = C.RAW / 'kamis'
    out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    for d in C.days(start, end):
        rows = []
        for mode, mname in (('02', '도매'), ('01', '소매')):
            for cat in ('100', '200', '300', '400'):
                p = {'action': 'dailyPriceByCategoryList', 'p_cert_key': kk, 'p_cert_id': kid, 'p_returntype': 'xml',
                     'p_product_cls_code': mode, 'p_item_category_code': cat, 'p_country_code': '',
                     'p_regday': d.isoformat(), 'p_convert_kg_yn': 'N'}
                try:
                    root = ET.fromstring(C.http_get(KAMIS_URL, p, secret=(kk, kid)).encode('utf-8')); calls += 1
                except ET.ParseError:
                    raise ApiFail('XML 아님')
                code = (root.findtext('.//error_code') or '').strip()
                if code == '001':
                    continue
                if code and code != '000':
                    raise ApiStop(f'KAMIS 오류코드 {code}')
                for it in root.findall('.//data/item'):
                    v = {c.tag: (c.text or '').strip() for c in it}
                    lab = v.get('day1', '')
                    mm = [int(x) for x in lab.replace('/', '-').replace('.', '-').split('-')[-2:] if x.isdigit()]
                    if len(mm) == 2 and (mm[0], mm[1]) != (d.month, d.day):
                        continue
                    pr = v.get('dpr1', '').replace(',', '')
                    rows.append([d.isoformat(), mname, cat, v.get('item_code', v.get('itemcode', '')), v.get('item_name', ''),
                                 v.get('kind_code', v.get('kindcode', '')), v.get('kind_name', ''),
                                 v.get('rank_code', v.get('rankcode', '')), v.get('rank', ''), v.get('unit', ''),
                                 pr if pr.replace('.', '').isdigit() else ''])
        with (out / f'{d8(d)}.csv').open('w', newline='', encoding='utf-8-sig') as fh:
            w = csv.writer(fh); w.writerow(KAMIS_FIELDS); w.writerows(rows)
        saved += len(rows)
        print(f'  KAMIS {d}: {len(rows):,}행', flush=True)
    return calls, saved


# ───────────────────────── 3. ASOS 일자료 (기상청 API허브) ─────────────────────────
APIHUB = 'https://apihub.kma.go.kr/api/typ01/url'


def text_of(b):
    for enc in ('utf-8', 'cp949', 'euc-kr'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode('utf-8', 'replace')


def months_between(start, end):
    m = start.replace(day=1)
    while m <= end:
        nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1)
        yield m, min(nxt - dt.timedelta(1), end)
        m = nxt


# ───────────────────────── 4. 기상특보 발표 이력 + 특보구역 (기상청 API허브) ─────────────────────────
def warning(start, end):
    k = C.key('KMA_APIHUB_KEY')
    out = C.RAW / 'warning'
    out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    reg = out / 'wrn_reg.txt'
    if not reg.exists() or (C.now().timestamp() - reg.stat().st_mtime) > 30 * 86400:  # 구역표는 30일마다
        reg.write_text(text_of(C.http_get(f'{APIHUB}/wrn_reg.php', {'disp': '1', 'authKey': k}, secret=(k,), raw=True)), encoding='utf-8'); calls += 1
    for a, b in months_between(start, end):
        a0 = a.replace(day=1)
        t = text_of(C.http_get(f'{APIHUB}/wrn_met_data.php', {'wrn': 'A', 'reg': '0', 'tmfc1': d8(a0) + '0000', 'tmfc2': d8(b) + '2359',
                                                              'disp': '1', 'authKey': k}, secret=(k,), timeout=120, raw=True)); calls += 1
        n = sum(1 for x in t.splitlines() if x[:1].isdigit())
        (out / f'{a:%Y-%m}.txt').write_text(t, encoding='utf-8'); saved += n
        print(f'  특보 {a:%Y-%m}: {n:,}줄', flush=True)
    return calls, saved


# ───────────────────────── 5. 날씨 (팀 collector/weather 를 그대로 넣음: weather/) ─────────────────────────
WX = C.HERE / 'weather'
WX_DATA = C.DATA / 'weather'


def _wx(args):
    """팀 날씨 수집기 run.py 실행. 키는 같은 이름(KMA_APIHUB_KEY·DATA_GO_KR_KEY)을 .env 에서 넘김"""
    import subprocess
    C.load_env()
    env = dict(__import__('os').environ, DATA_DIR=str(WX_DATA), PYTHONUTF8='1')
    WX_DATA.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, '-X', 'utf8', str(WX / 'run.py')] + args, cwd=str(WX), env=env)
    if r.returncode in (2, 3):
        raise ApiStop(f'날씨 수집기 종료코드 {r.returncode} (2 키 없음 · 3 인증 오류) → data/weather/collect_log.json')
    if r.returncode != 0:
        raise ApiFail(f'날씨 수집기 종료코드 {r.returncode} → data/weather/collect_log.json')
    return 0, 0


def weather(start=None, end=None):
    """ASOS·AWS·농업기상·장기전망 받고 → 기상 통합 전처리 → 날씨_대통합_일별.csv (시·도·시군구 일별 + 평년)"""
    return _wx(['all', '--only', 'asos,aws,agri,longrange'])


def fcst(start=None, end=None):
    """단기·중기예보. 3시간마다 돌려야 빠짐없이 받음 (API가 최근 24시간 발표분만 줌)
    처음 한 번은 218격자 × 최근 발표 최대 8번 = 약 1,700회라 20~40분 걸림. 그다음부터는 새 발표분만(3시간마다 약 230회)"""
    return _wx(['collect', '--only', 'fcst'])


def fcst_probe(start=None, end=None):
    """연결시험용: 격자 1개 + 중기 구역 1개만 (팀 collect_fcst.py --probe)"""
    import subprocess
    C.load_env()
    env = dict(__import__('os').environ, DATA_DIR=str(WX_DATA), PYTHONUTF8='1')
    d = WX_DATA / 'raw' / 'fcst'; d.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, '-X', 'utf8', str(WX / 'collect_fcst.py'), '--probe', '--data', str(d)], cwd=str(WX), env=env, timeout=300)
    if r.returncode != 0:
        raise ApiFail(f'예보 시험 종료코드 {r.returncode} (2 키 없음 · 3 인증·활용신청 확인)')
    return 4, 0


# ───────────────────────── 6. 특일 정보 (한국천문연구원, 공공데이터포털) ─────────────────────────
HOLI_URL = 'http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo'


def holiday(start=None, end=None):
    """올해·내년 공휴일 (매일 돌 필요 없음: 파일이 30일 넘으면 다시)"""
    k = C.key('DATA_GO_KR_KEY')
    out = C.RAW / 'holiday'
    out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    y0 = C.today().year
    for y in sorted({start.year if start else y0, y0, y0 + 1}):
        f = out / f'{y}.json'
        if f.exists() and (C.now().timestamp() - f.stat().st_mtime) < 30 * 86400:
            continue
        items = []
        for m in range(1, 13):
            txt = C.http_get(HOLI_URL, {'ServiceKey': k, 'solYear': y, 'solMonth': f'{m:02d}', '_type': 'json', 'numOfRows': 50}, secret=(k,)); calls += 1
            try:
                body = json.loads(txt)['response']['body']
            except (json.JSONDecodeError, KeyError):
                raise ApiStop('특일 응답 이상 (활용신청 확인): ' + C._mask(txt[:120], (k,)))
            it = (body.get('items') or {}) if isinstance(body.get('items'), dict) else {}
            it = it.get('item', [])
            items += [it] if isinstance(it, dict) else it
        f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8'); saved += len(items)
        print(f'  특일 {y}: {len(items)}일', flush=True)
    return calls, saved


# ───────────────────────── 7. 산지공판장 정산 (농식품부, 건별) ─────────────────────────
SANJI_GRID = 'Grid_20240625000000000660_1'
SANJI_KOR = {'SALEDATE': '정산일자', 'CMPCD': '법인_공판장코드', 'CMPNAME': '법인_공판장명', 'LARGE': '대분류코드', 'MID': '중분류코드',
             'SMALL': '소분류코드', 'PUMNAME': '품목명', 'GOODNAME': '품종명', 'DANQ': '단위중량', 'LVCD': '등급코드', 'SANNAME': '산지명',
             'TOTQTY': '총물량', 'TOTAMT': '총금액'}   # 출하자·중도매인·수집상 코드와 이름은 저장 안 함


def sanji(start, end, recheck=10):
    """공판장 자료는 늦게 올라와(45일) 최근 recheck 일과 '자료없음'은 다시 확인. 2026-09-03 뒤로 새 자료가 아직 없음(11-06 기준)"""
    k = C.key('MAFRA_API_KEY')
    st = C.state('sanji')
    out = C.RAW / 'sanji'; out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    cut = d8(C.today() - dt.timedelta(45))
    for d in C.days(start, end):
        ds = d8(d)
        if st.get(ds) == 'ok' or (st.get(ds) == 'no_data' and ds < cut):
            continue
        try:
            total, rows = mafra_call(k, 1, 1000, {'SALEDATE': ds}, SANJI_GRID); calls += 1
            s = 1001
            while len(rows) < total:
                _, more = mafra_call(k, s, s + 999, {'SALEDATE': ds}, SANJI_GRID); calls += 1
                if not more:
                    raise ApiFail('빈 페이지')
                rows += more; s += 1000
            st[ds] = 'ok' if rows else 'no_data'
        except ApiFail as e:
            st[ds] = 'failed'; print(f'  산지 {ds} 실패: {e}', flush=True); rows = []
        if rows:
            with gzip.open(out / f'{ds}.csv.gz', 'wt', encoding='utf-8-sig', newline='') as fh:
                w = csv.DictWriter(fh, fieldnames=list(SANJI_KOR.values())); w.writeheader()
                w.writerows({SANJI_KOR[c]: r.get(c, '') for c in SANJI_KOR} for r in rows)
            saved += len(rows)
        C.save_state('sanji', st)
        print(f'  산지공판장 {ds}: {len(rows):,}행 ({st[ds]})', flush=True)
    return calls, saved


# ───────────────────────── 8. 가락시장 경매전·경매후 반입물량 (서울 열린데이터광장, 단위 톤) ─────────────────────────
SEOUL = 'http://openapi.seoul.go.kr:8088'


def garak_inout(start=None, end=None):
    """API가 기간 조건 없이 전체(2023-05-16~)를 돌려줌 → 매일 전체를 받아 덮어씀 (서비스마다 약 100쪽)"""
    import urllib.parse
    k = C.key('SEOUL_OPENAPI_KEY')
    out = C.RAW / 'garak_inout'; out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    for svc in ('GarakAuctionBefore', 'GarakAuctionAfter'):
        rows, s, total = [], 1, None
        while total is None or s <= total:
            url = f'{SEOUL}/{urllib.parse.quote(k, safe="")}/json/{svc}/{s}/{s + 999}/'
            js = json.loads(C.http_get(url, secret=(k,), timeout=60)); calls += 1
            body = js.get(svc)
            if not isinstance(body, dict):
                code = js.get('RESULT', {}).get('CODE', '?')
                raise (ApiStop if code.startswith('ERROR-3') or code == 'INFO-100' else ApiFail)(f'{svc} {code}')
            total = int(body.get('list_total_count', 0))
            rows += body.get('row', []) or []
            s += 1000
        if len(rows) != total:
            raise ApiFail(f'{svc} 행수 불일치 {len(rows)}/{total}')
        f = out / f'{svc}.csv'; tmp = f.with_suffix('.tmp')
        cols = list(dict.fromkeys(c for r in rows for c in r))
        with tmp.open('w', newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
        tmp.replace(f); saved += len(rows)
        print(f'  가락 {svc}: {len(rows):,}행', flush=True)
    return calls, saved


# ───────────────────────── 9. aT 도매시장 출하예약 (전자송품장, data.go.kr 15141813 자동승인) ─────────────────────────
ATRESV_URL = 'https://apis.data.go.kr/B552845/katElectronicInvoice2/shipmentReservations2'
ATRESV_COLS = ['spmt_dt', 'whsl_mrkt_cd', 'whsl_mrkt_nm', 'corp_cd', 'corp_nm', 'gds_lclsf_cd', 'gds_lclsf_nm', 'gds_mclsf_cd', 'gds_mclsf_nm',
               'gds_sclsf_cd', 'gds_sclsf_nm', 'spmt_qty', 'unit_qty', 'unit_cd', 'unit_nm', 'pkg_cd', 'pkg_nm', 'grd_cd', 'grd_nm',
               'einvc_stts', 'trd_type', 'trd_se']   # 송장번호(einvc_no) 는 저장 안 함


def at_resv(start, end):
    """출하예정일 기준. 지난 14일(늦은 입력 반영) + 오늘~3일 뒤(미리 들어온 예약)를 매일 다시 받음"""
    k = C.key('DATA_GO_KR_KEY')
    out = C.RAW / 'at_resv'; out.mkdir(parents=True, exist_ok=True)
    calls = saved = 0
    for d in C.days(start, end + dt.timedelta(3)):
        rows, page, total = [], 1, None
        while total is None or len(rows) < total:
            txt = C.http_get(ATRESV_URL, {'serviceKey': k, 'pageNo': page, 'numOfRows': 1000, 'returnType': 'json', 'cond[spmt_dt::EQ]': d.isoformat()},
                             secret=(k,), timeout=120); calls += 1
            if 'LIMITED_NUMBER_OF_SERVICE_REQUESTS' in txt.upper():
                raise ApiStop('일일 호출 한도')
            try:
                resp = json.loads(txt).get('response', {})
            except json.JSONDecodeError:
                raise ApiStop('JSON 아님 (인증키·활용신청 확인): ' + C._mask(txt[:120], (k,)))
            code = str(resp.get('header', {}).get('resultCode', '00'))
            if code in ('03', 'INFO-200'):
                total = 0; break
            if code not in ('00', '0', '000', 'INFO-000', 'NORMAL_SERVICE', ''):
                raise ApiFail(f'resultCode {code}')
            body = resp.get('body', {}) or {}
            it = body.get('items') or {}
            it = it.get('item', []) if isinstance(it, dict) else it
            it = [it] if isinstance(it, dict) else (it or [])
            total = int(body.get('totalCount') or 0)
            if not it:
                break
            rows += it; page += 1
        with (out / f'{d.isoformat()}.csv').open('w', newline='', encoding='utf-8-sig') as fh:
            w = csv.DictWriter(fh, fieldnames=ATRESV_COLS + ['수집시각'], extrasaction='ignore'); w.writeheader()
            stamp = C.now().isoformat(timespec='seconds')
            w.writerows(dict(r, 수집시각=stamp) for r in rows)
        saved += len(rows)
        print(f'  aT 출하예약 {d}: {len(rows):,}행', flush=True)
    return calls, saved


# ───────────────────────── 10. 환율 (한국은행 ECOS 731Y001 일별 매매기준율) ─────────────────────────
ECOS = 'https://ecos.bok.or.kr/api'
FX_WANT = ('미국달러', '위안', '일본엔', '유로')


def fx(start, end):
    import urllib.parse
    k = C.key('ECOS_API_KEY')
    out = C.RAW / 'fx'; out.mkdir(parents=True, exist_ok=True)
    q = urllib.parse.quote(k, safe='')
    calls = 0
    meta = out / 'items.json'
    if not meta.exists():
        js = json.loads(C.http_get(f'{ECOS}/StatisticItemList/{q}/json/kr/1/1000/731Y001', secret=(k,))); calls += 1
        items = js.get('StatisticItemList', {}).get('row', [])
        if not items:
            raise ApiStop('ECOS 항목 목록 실패 (키 확인): ' + str(js.get('RESULT', ''))[:100])
        meta.write_text(json.dumps(items, ensure_ascii=False), encoding='utf-8')
    items = [r for r in json.loads(meta.read_text(encoding='utf-8')) if r.get('CYCLE') == 'D' and any(w in r.get('ITEM_NAME', '') for w in FX_WANT)
             and ('매매기준율' in r.get('ITEM_NAME', '') or r.get('ITEM_NAME') == '원/일본엔(100엔)')]
    f = out / 'fx_daily.csv'
    old = {}
    if f.exists():
        old = {(r['date'], r['item_code']): r for r in read_csv(f)}
    for it in items:
        s = 1
        while True:
            js = json.loads(C.http_get(f'{ECOS}/StatisticSearch/{q}/json/kr/{s}/{s + 999}/731Y001/D/{d8(start)}/{d8(end)}/{it["ITEM_CODE"]}', secret=(k,))); calls += 1
            b = js.get('StatisticSearch')
            if not b:
                if js.get('RESULT', {}).get('CODE') == 'INFO-200':
                    break
                raise ApiFail('ECOS ' + str(js.get('RESULT', ''))[:100])
            for r in b.get('row', []):
                t = r['TIME']
                old[(f'{t[:4]}-{t[4:6]}-{t[6:]}', it['ITEM_CODE'])] = {'date': f'{t[:4]}-{t[4:6]}-{t[6:]}', 'item_code': it['ITEM_CODE'],
                                                                     'item_name': it['ITEM_NAME'], 'value': r.get('DATA_VALUE', '')}
            if s + 999 >= int(b['list_total_count']):
                break
            s += 1000
    with f.open('w', newline='', encoding='utf-8-sig') as fh:
        w = csv.DictWriter(fh, fieldnames=['date', 'item_code', 'item_name', 'value']); w.writeheader()
        w.writerows(sorted(old.values(), key=lambda r: (r['date'], r['item_code'])))
    print(f'  환율 {start}~{end}: 항목 {len(items)}개, 누적 {len(old):,}행', flush=True)
    return calls, len(old)


# ───────────────────────── 11. 정부 수급정책 보도자료·공고 (농식품부·aT 누리집, 키 없음) ─────────────────────────
def policy(start=None, end=None):
    """NongClock 정부정책 수집기(policy/) 의 목록 앞 3쪽만 다시 보고 새 문서·첨부만 받음 → data/policy/01_전체문서_수집목록.csv"""
    import subprocess
    r = subprocess.run([sys.executable, '-X', 'utf8', str(C.HERE / 'policy' / 'latest.py'), '3', str(C.DATA / 'policy')],
                       cwd=str(C.HERE / 'policy'))
    if r.returncode != 0:
        raise ApiFail(f'정책 수집기 종료코드 {r.returncode}')
    return 0, 0


# ───────────────────────── 실행 ─────────────────────────
JOBS = {  # 이름: (함수, 기본 시작일 = 오늘에서 며칠 전, 설명)
    'auction': (auction, 10, '공영도매시장 정산가격(전날까지)'),
    'kamis': (kamis, 21, 'KAMIS 도·소매(오늘까지, 21일 다시 확인)'),
    'warning': (warning, 3, '기상특보 발표 이력'),
    'weather': (weather, 0, '날씨 관측(ASOS·AWS·농업기상)·장기전망 + 통합 전처리 (팀 날씨 수집기)'),
    'fcst': (fcst, 0, '단기·중기예보 (팀 날씨 수집기, 3시간마다)'),
    'holiday': (holiday, 0, '특일(올해·내년)'),
    'sanji': (sanji, 45, '산지공판장 정산(늦게 올라와 45일 다시 확인)'),
    'garak_inout': (garak_inout, 0, '가락 경매전·후 반입물량(전체 다시)'),
    'at_resv': (at_resv, 14, 'aT 도매시장 출하예약(지난 14일 + 앞으로 3일)'),
    'fx': (fx, 10, '환율(ECOS)'),
    'policy': (policy, 0, '정부 수급정책 보도자료·공고'),
}


def last_got(name):
    """그 자료를 마지막으로 받은 날 (없으면 None)"""
    if name in ('auction', 'sanji'):
        ok = [k for k, v in C.state(name).items() if (v == 'ok' if isinstance(v, str) else 'ok' in v.values())]
        return dt.datetime.strptime(max(ok), '%Y%m%d').date() if ok else None
    if name in ('kamis', 'at_resv'):
        fs = sorted(p.stem.replace('-', '') for p in (C.RAW / name).glob('*.csv'))
        return dt.datetime.strptime(fs[-1][:8], '%Y%m%d').date() if fs else None
    if name == 'warning':
        fs = sorted(p.stem for p in (C.RAW / name).glob('20*.txt'))
        return dt.date.fromisoformat(fs[-1] + '-01') if fs else None
    return None


def run(name, start, end):
    fn, _, desc = JOBS[name]
    t0 = C.now()
    print(f'[{name}] {desc}  {start} ~ {end}', flush=True)
    try:
        calls, saved = fn(start, end)
        C.write_log(name, t0, True, rows_saved=saved, api_calls=calls)
        return True
    except (ApiStop, ApiFail, SystemExit) as e:
        print(f'  ✗ {name}: {e}', flush=True)
        C.write_log(name, t0, False, error=str(e))
        return False


def test():
    """자료마다 아주 작게 한 번씩 불러 봄"""
    y = YDAY()
    ok = {}
    tests = {'auction': (y, y), 'kamis': (y, y), 'warning': (y, y), 'holiday': (None, None), 'fcst': (None, None),
             'sanji': (y, y), 'at_resv': (y, y - dt.timedelta(3)), 'fx': (y - dt.timedelta(7), y), 'garak_inout': (None, None)}
    for name, (s, e) in tests.items():
        if name == 'fcst':   # 예보 전체(약 1,700회)를 받지 않고 1격자만
            t0 = C.now(); print('[fcst] 단기·중기예보 연결시험 (격자 1개)', flush=True)
            try:
                calls, _ = fcst_probe(); C.write_log('fcst_test', t0, True, api_calls=calls); ok[name] = True
            except (ApiStop, ApiFail, Exception) as ex:
                print(f'  ✗ fcst: {ex}', flush=True); C.write_log('fcst_test', t0, False, error=str(ex)); ok[name] = False
            continue
        ok[name] = run(name, s, e)
    print('\n시험 결과:', ', '.join(f'{k} {"성공" if v else "실패"}' for k, v in ok.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job', choices=['test', 'daily'] + list(JOBS))
    ap.add_argument('--backfill', action='store_true', help='weather: 날씨 과거 전체 (팀 run.py collect --backfill)')
    ap.add_argument('--start'); ap.add_argument('--end')
    a = ap.parse_args()
    if a.job == 'test':
        return test()
    if a.job == 'weather' and a.backfill:
        return _wx(['collect', '--backfill', '--only', 'asos,aws,agri']) and None
    names = list(JOBS) if a.job == 'daily' else [a.job]
    bad = []
    for n in names:
        back = JOBS[n][1]
        end = dt.date.fromisoformat(a.end) if a.end else (C.today() if n in ('kamis', 'fcst', 'holiday', 'weather', 'garak_inout', 'at_resv', 'policy') else YDAY())
        start = dt.date.fromisoformat(a.start) if a.start else end - dt.timedelta(back)
        if not a.start:
            last = last_got(n)
            if last and last + dt.timedelta(1) < start:   # 며칠 못 돌렸으면 마지막으로 받은 다음 날부터
                start = last + dt.timedelta(1)
        if not run(n, start, end):
            bad.append(n)
    if bad:
        print('실패:', ', '.join(bad), '— data/log/collect_log.csv 확인'); sys.exit(1)


if __name__ == '__main__':
    main()
