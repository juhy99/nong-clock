"""기상청 API허브 '지상 및 AWS 일통계 - 요소별 조회'(sfc_aws_day.php)로 전국 ASOS+AWS 일자료를 1년 단위로 수집.
호출 수 = 요소 5개 x 연도 수 (2015~2026 → 60번). 이미 받은 연도·요소는 건너뜀(이어받기).
결과: AWS_일자료_전국/
  원본/{요소}_{연도}.txt.gz        API 응답 원문(인증키 없음)
  요소별/{요소}.csv                날짜,지점,값 (long)
  AWS_ASOS_일자료_전국통합.csv      날짜×지점 1행, 최고·최저기온, 강수, 최대·순간최대풍속 + 위경도·고도·지점명
  수집현황.csv / 수집요약.json
원래 파일: AWS_일자료_전국_빠른수집.py (리눅스 서버용으로 경로·키 읽기만 바꿈)
실행: python collect_aws.py --start <연도> --out data/raw/aws   (보통은 run.py가 실행)
인증키: 환경변수 KMA_APIHUB_KEY (ASOS와 같은 기상청 API허브 키, 이 API도 API허브에서 활용신청 필요)
서버판 수정: '어제가 속한 연도' 파일은 있어도 매번 다시 받음(원본은 연도 단위라 새 날짜가 들어오게).
"""
import argparse, csv, datetime as dt, gzip, io, json, os, pathlib, sys, time
import wxcommon  # urlopen 호출 수 세기 — urllib import보다 먼저
import urllib.parse, urllib.request, urllib.error

BASE = wxcommon.KMA_APIHUB_BASE + '/api/typ01/url/sfc_aws_day.php'
OBS = {'ta_max': '최고기온', 'ta_min': '최저기온', 'rn_day': '강수량', 'ws_max': '최대풍속', 'ws_ins_max': '최대순간풍속'}


def fetch(key, obs, y1, y2):
    q = urllib.parse.urlencode(dict(tm1=y1, tm2=y2, obs=obs, stn='0', disp='1', help='0', authKey=key))
    with urllib.request.urlopen(BASE + '?' + q, timeout=300) as r:
        return r.read()


def parse(raw):
    text = raw.decode('cp949', errors='replace')
    if '#START7777' not in text:
        raise RuntimeError('정상 응답 아님: ' + text[:200].replace('\n', ' '))
    rows = []
    for line in text.splitlines():
        if not line or line.startswith('#'):
            continue
        p = line.split(',')
        if len(p) < 7:
            continue
        rows.append((p[0], p[1], p[2], p[3], p[4], p[5], p[6].rstrip('=').strip()))
    return rows, ('#7777END' in text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', type=int, default=2015)
    ap.add_argument('--end', type=int, default=None, help='마지막 연도(기본: 어제 기준 연도)')
    ap.add_argument('--out', default=str(wxcommon.data_dir() / 'raw' / 'aws'))
    ap.add_argument('--merge-only', action='store_true', help='API 호출 없이 받은 원본으로 통합파일만 다시 만들기')
    a = ap.parse_args()
    yesterday = (dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date() - dt.timedelta(days=1))
    end = a.end or yesterday.year
    out = pathlib.Path(a.out); raw_dir = out / '원본'; raw_dir.mkdir(parents=True, exist_ok=True)
    status = []

    if not a.merge_only:
        wxcommon.start()
        key = wxcommon.get_key('KMA_APIHUB_KEY', ('KMA_AUTH_KEY',))
        if not key:
            wxcommon.exit_nokey('KMA_APIHUB_KEY')
        for obs in OBS:
            for y in range(a.start, end + 1):
                f = raw_dir / f'{obs}_{y}.txt.gz'
                old_rows = 0
                if f.exists():
                    if y != yesterday.year:
                        print(f'{obs} {y}: 이미 있음, 건너뜀'); continue
                    old_rows = len(parse(gzip.decompress(f.read_bytes()))[0])   # 올해 파일은 다시 받음
                y2 = f'{y}1231' if y < yesterday.year else yesterday.strftime('%Y%m%d')
                for attempt in range(4):
                    try:
                        raw = fetch(key, obs, f'{y}0101', y2)
                        rows, complete = parse(raw)
                        if not complete:
                            raise RuntimeError('응답 끝(#7777END) 없음: 잘린 응답')
                        days = len({r[0] for r in rows})
                        tmp = f.with_name(f.name + '.part')          # 중간에 끊겨도 예전 파일은 그대로
                        tmp.write_bytes(gzip.compress(raw.replace(key.encode(), b'[KEY]')))
                        os.replace(tmp, f)
                        wxcommon.STATS['added'] += len(rows) - old_rows
                        print(f'{obs} {y}: {len(rows):,}행, {days}일', flush=True); break
                    except urllib.error.HTTPError as e:
                        body = e.read().decode('utf-8', errors='replace')[:200]
                        if e.code == 403 or e.code == 401:
                            print(f'중지: HTTP {e.code} {body}', flush=True)
                            finish(out, raw_dir, a, end)
                            wxcommon.exit_auth(f'HTTP {e.code} {body[:120]}')
                        print(f'{obs} {y}: HTTP {e.code}, 재시도 {attempt+1}/4', flush=True); time.sleep(5 * (attempt + 1))
                    except Exception as e:
                        print(f'{obs} {y}: {e} 재시도 {attempt+1}/4', flush=True); time.sleep(5 * (attempt + 1))
                else:
                    print(f'{obs} {y}: 실패(다음 실행 때 다시 시도)', flush=True)
                    wxcommon.error(f'AWS {obs} {y}: 4회 실패')
                time.sleep(1)
    finish(out, raw_dir, a, end)


def finish(out, raw_dir, a, end):
    import pandas as pd
    (out / '요소별').mkdir(exist_ok=True)
    meta, wide, status = [], None, []
    for obs, name in OBS.items():
        parts = []
        for y in range(a.start, end + 1):
            f = raw_dir / f'{obs}_{y}.txt.gz'
            if not f.exists():
                status.append({'요소': obs, '연도': y, '상태': '미수집', '행수': 0, '일수': 0}); continue
            rows, complete = parse(gzip.decompress(f.read_bytes()))
            df = pd.DataFrame(rows, columns=['날짜', '지점', '경도', '위도', '고도', name, '지점명'])
            status.append({'요소': obs, '연도': y, '상태': 'ok' if complete else '잘림', '행수': len(df), '일수': df['날짜'].nunique()})
            parts.append(df)
        if not parts:
            continue
        df = pd.concat(parts, ignore_index=True)
        df['날짜'] = pd.to_datetime(df['날짜'], format='%Y%m%d')
        df['지점'] = df['지점'].astype(int)
        df[name] = pd.to_numeric(df[name], errors='coerce')
        df.loc[df[name] <= -50, name] = float('nan')          # 결측코드(-99 등) 방어
        df = df.drop_duplicates(['날짜', '지점'], keep='last')
        df[['날짜', '지점', name]].to_csv(out / '요소별' / f'{obs}.csv', index=False, encoding='utf-8-sig', date_format='%Y-%m-%d')
        meta.append(df[['날짜', '지점', '경도', '위도', '고도', '지점명']])
        v = df[['날짜', '지점', name]]
        wide = v if wide is None else wide.merge(v, on=['날짜', '지점'], how='outer')
    pd.DataFrame(status).to_csv(out / '수집현황.csv', index=False, encoding='utf-8-sig')
    if wide is None:
        print('통합할 자료 없음'); return
    m = pd.concat(meta).sort_values('날짜').drop_duplicates(['날짜', '지점'], keep='last')   # 그날의 지점 위치
    wide = wide.merge(m, on=['날짜', '지점'], how='left')
    cols = ['날짜', '지점', '지점명', '위도', '경도', '고도'] + [n for n in OBS.values() if n in wide]
    wide = wide[cols].sort_values(['날짜', '지점'])
    wide.to_csv(out / 'AWS_ASOS_일자료_전국통합.csv', index=False, encoding='utf-8-sig', date_format='%Y-%m-%d')
    summary = {'행수': len(wide), '지점수': int(wide['지점'].nunique()),
               '기간': [str(wide['날짜'].min().date()), str(wide['날짜'].max().date())],
               '요소별_결측비율(%)': {n: round(float(wide[n].isna().mean() * 100), 2) for n in OBS.values() if n in wide},
               '미수집': [f"{s['요소']}_{s['연도']}" for s in status if s['상태'] != 'ok'],
               '주의': 'ASOS 지점(90~295 등)도 포함됨. 강수량은 값이 있는 지점만 응답에 나옴(무강수 0 포함 여부는 지점별로 다를 수 있음). 평균기온은 이 API에 없음.'}
    (out / '수집요약.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
    if wxcommon.STATS['errors']:
        sys.exit(wxcommon.EXIT_FAIL)
