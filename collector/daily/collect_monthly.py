# -*- coding: utf-8 -*-
"""1년 모델용 추가 자료 받기 (일일 수집 collect.py 에 없는 것). 2026-11-13
  python collect_monthly.py all        # 아래를 차례로 (자동실행.py 가 매일 부름 — 이미 받은 것은 건너뜀)
  python collect_monthly.py juju       # 농업주산지 기상 일통계 (data.go.kr 15059518, DATA_GO_KR_KEY — 활용신청 필요): 이번 달·지난달
  python collect_monthly.py juju --start 2015-01   # 과거부터
  python collect_monthly.py kosis      # 통계청 면적·생산 (KOSIS OpenAPI, .env 의 KOSIS_API_KEY). 한 달에 한 번
  python collect_monthly.py wolbo      # 관측월보: 자동으로 못 받음(robots). 이번 달 호 PDF 를 넣었는지만 확인하고 없으면 알림
결과: data/raw/juju/YYYYMM.json(.gz) · data/manual/월보/ (사람이 넣는 곳)
"""
import argparse, datetime as dt, gzip, json, os, subprocess, sys
import common as C
from common import ApiFail, ApiStop
DATA = getattr(C, 'DATA', C.HERE / 'data')

def juju(start=None):
    """한 달씩. 지난 달은 한 번 성공하면 다시 안 받고, 이번 달과 지난달은 매번 다시 받음"""
    k = C.key('DATA_GO_KR_KEY'); out = C.RAW / 'juju'; out.mkdir(parents=True, exist_ok=True); st = C.state('juju')
    today = C.today(); first = dt.date(int(start[:4]), int(start[5:7]), 1) if start else (today.replace(day=1) - dt.timedelta(1)).replace(day=1)
    m = first; calls = saved = 0
    while m <= today:
        nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1); ym = f'{m:%Y%m}'; end = min(nxt - dt.timedelta(1), today - dt.timedelta(1))
        recent = (today - m).days < 62
        if end >= m and (recent or st.get(ym) != 'ok'):
            rows = []; page = 1
            while True:
                txt = C.http_get('https://apis.data.go.kr/1360000/FmlandWthrInfoService/getDayStatistics',
                                 {'serviceKey': k, 'pageNo': page, 'numOfRows': 1000, 'dataType': 'JSON', 'ST_YMD': f'{m:%Y%m%d}', 'ED_YMD': f'{end:%Y%m%d}', 'AREA_ID': '999999999', 'PA_CROP_SPE_ID': 'PA999999'},
                                 secret=(k,), timeout=180); calls += 1
                if 'SERVICE_KEY_IS_NOT_REGISTERED' in txt or 'SERVICE ACCESS DENIED' in txt.upper(): raise ApiStop('data.go.kr 15059518 활용신청이 없거나 인증키가 다름')
                try: js = json.loads(txt)
                except json.JSONDecodeError: raise ApiFail('JSON 아님: ' + txt[:80].replace('\n', ' '))
                h = js.get('response', {}).get('header', {}); code = str(h.get('resultCode', ''))
                if code == '03': break
                if code not in ('00', '0', '0000'): raise ApiFail(f"{code} {h.get('resultMsg', '')}")
                b = js['response'].get('body', {}); it = b.get('items') or {}; it = it.get('item', []) if isinstance(it, dict) else it
                it = [it] if isinstance(it, dict) else it; rows += it
                if len(rows) >= int(b.get('totalCount') or 0) or not it: break
                page += 1
            if rows:
                with gzip.open(out / f'{ym}.json.gz', 'wt', encoding='utf-8') as f: json.dump(rows, f, ensure_ascii=False)
                saved += len(rows)
            st[ym] = 'ok' if rows else 'no_data'; C.save_state('juju', st); print(f'  juju {ym}: {len(rows):,}줄', flush=True)
        m = nxt
    return calls, saved

def kosis(_=None):
    """통계청 면적·생산 14개 표 (kosis/kosis_auto.py — 이 폴더에 들어 있음). 한 달에 한 번, 최근 3년만 다시 받음"""
    C.load_env()
    if not os.getenv('KOSIS_API_KEY', '').strip(): raise ApiStop('인증키 KOSIS_API_KEY 가 없습니다. .env 에 KOSIS_API_KEY=... 를 넣으세요 (kosis.kr 공유서비스)')
    f = C.RAW / 'kosis_마지막.txt'; last = f.read_text(encoding='utf-8').strip() if f.exists() else ''
    if last == f'{C.today():%Y-%m}': print('  kosis: 이번 달 이미 확인함'); return 0, 0
    out = C.RAW / 'kosis'; out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, '-X', 'utf8', '-u', 'kosis_auto.py', '--start', f'{C.today().year - 2}-01-01'], cwd=str(C.HERE / 'kosis'), env=dict(os.environ, KOSIS_OUT=str(out)))
    if r.returncode != 0: raise ApiFail(f'KOSIS 수집기 종료코드 {r.returncode}')
    f.write_text(f'{C.today():%Y-%m}', encoding='utf-8'); return 0, 0

def wolbo(_=None):
    d = DATA / 'manual' / '월보'; d.mkdir(parents=True, exist_ok=True); ym = f'{C.today():%Y%m}'; ym2 = f'{C.today():%Y-%m}'
    got = [p.name for p in d.iterdir() if ym in p.name or ym2 in p.name]
    if got: print(f'  wolbo: 이번 달 호 있음 ({len(got)}개)'); return 0, len(got)
    if C.today().day >= 10: raise ApiFail(f'[없음] 관측월보 {ym2} 호가 {d} 에 없습니다. aglook.krei.re.kr 에서 내려받아 넣어 주세요 (파일 이름에 {ym} 포함)')
    print('  wolbo: 이번 달 호 아직 없음 (10일부터 알림)'); return 0, 0

JOBS = {'juju': juju, 'kosis': kosis, 'wolbo': wolbo}
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('job', choices=['all'] + list(JOBS)); ap.add_argument('--start'); a = ap.parse_args(); bad = []
    for n in (list(JOBS) if a.job == 'all' else [a.job]):
        t0 = C.now(); print(f'[{n}]', flush=True)
        try:
            calls, saved = JOBS[n](a.start); C.write_log(n, t0, True, rows_saved=saved, api_calls=calls)
        except (ApiStop, ApiFail, SystemExit) as e:
            print(f'  ✗ {n}: {e}', flush=True); C.write_log(n, t0, False, error=str(e)); bad.append(n)
    if bad: print('실패:', ', '.join(bad)); sys.exit(1)
if __name__ == '__main__':
    main()
