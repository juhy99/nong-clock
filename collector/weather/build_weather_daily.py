r"""날씨 대통합(일별) 만들기 — 2026-10-22 v2 (모든 지역 일별로 통일)

입력: 기상 통합 03_연결 폴더 (기상_통합_전처리.py 결과)
  - 시도별_일기상.csv          (1991-01-01 ~)
  - 일자료_연도별/{YYYY}.csv     (관측소×일, 시도·시군구 붙음, 품질 점검 끝난 값)
  - 관측지점_마스터.csv          (좌표)
출력: 날씨_대통합_일별.csv, 점검.json

구분
  시도_일   : 17개 시도 × 일, 1991-01-01 ~  (시도별_일기상 그대로)
  시군구_일 : 시군구 × 일, --sgg-start(기본 2015-01-01) ~  (그 시군구 관측소 단순평균, 시도_일과 같은 방식)
              구가 있는 일반시(수원·성남·고양·용인·안산·안양·청주·천안·전주·포항·창원 등)는 시 단위로 합침
평년(시도_일만): 1991~2020년 같은 월·일 ±3일(7일×30년) 평균 → 평년_평균기온·평년_최고기온·평년_최저기온·평년_강수량
행 기준: 날씨 값 3개 이상 있는 행만

사용: python build_weather_daily.py --link <03_연결 폴더> --out <출력 폴더> [--cache <중간파일 폴더>]
      (환경변수 WEATHER_LINK_DIR, WEATHER_OUT_DIR 도 됨. 둘 다 없으면 DATA_DIR/link, DATA_DIR/site)
주의: 시군구 중간파일(<out>/_중간/sgg_{연도}.csv)은 있으면 다시 안 만듦 → run.py preprocess가 올해 것을 지우고 실행
"""
import argparse, json, os
from pathlib import Path
import numpy as np, pandas as pd

V = ['평균기온', '평균기온_근사', '최고기온', '최저기온', '강수량', '평균습도', '일조시간', '일사량', '최대풍속', '최대순간풍속']
COLS = ['구분', '날짜', '시도', '시군구', '위도', '경도'] + V + ['평년_평균기온', '평년_최고기온', '평년_최저기온', '평년_강수량',
        '지점수', '지점수_ASOS', '지점수_AWS', '지점수_농업기상', '값개수']
NV = ['평균기온', '최고기온', '최저기온', '강수량', '평균습도', '일조시간', '일사량', '최대풍속', '최대순간풍속']   # 값개수 셀 때(근사 제외)


def norm_sgg(x):
    """'수원시 권선구' → '수원시' (구가 있는 일반시는 시 단위로 통일. 농업기상 지점은 원래 시 단위로만 붙어 있어
    같은 시가 '수원시'·'수원시 권선구'로 갈라지던 문제). 광역시 구(대구 북구 등)는 그대로."""
    if isinstance(x, str) and ' ' in x and x.split()[0].endswith('시'): return x.split()[0]
    return x


def norm(df):
    df['시군구'] = df['시군구'].map(norm_sgg)
    df.loc[df['시도'] == '세종', '시군구'] = '세종시'   # 세종은 시군구가 없음(새롬동·세종리 등 동 이름이 붙어 있던 것)
    return df


def sgg_year(link, y, cache):
    f = cache / f'sgg_{y}.csv'
    if f.exists(): return pd.read_csv(f, dtype={'시도': str, '시군구': str})
    d = pd.read_csv(link / '일자료_연도별' / f'{y}.csv', usecols=['날짜', '관측망', '지점', '시도', '시군구'] + V,
                    dtype={'지점': str, '시도': str, '시군구': str}, encoding='utf-8-sig')
    d = d[d['시도'].notna() & d['시군구'].notna()]
    d = norm(d)
    for net in ('ASOS', 'AWS', '농업기상'):
        d['n_' + net] = ((d['관측망'] == net) & d['최고기온'].notna()).astype(int)
    g = d.groupby(['시도', '시군구', '날짜']).agg(**{v: (v, 'mean') for v in V}, 지점수=('최고기온', 'count'),
                                                  지점수_ASOS=('n_ASOS', 'sum'), 지점수_AWS=('n_AWS', 'sum'),
                                                  지점수_농업기상=('n_농업기상', 'sum')).round(2).reset_index()
    g.to_csv(f, index=False, encoding='utf-8')
    return g


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    dd = Path(os.getenv('DATA_DIR') or 'data')
    dd = dd if dd.is_absolute() else Path(__file__).resolve().parent / dd
    ap.add_argument('--link', default=os.getenv('WEATHER_LINK_DIR', str(dd / 'link')))
    ap.add_argument('--out', default=os.getenv('WEATHER_OUT_DIR', str(dd / 'site')))
    ap.add_argument('--cache', default='')
    ap.add_argument('--sgg-start', default='2015-01-01')
    ap.add_argument('--years', default='', help='시군구 중간파일만 이 연도들 만들고 끝 (예: 2015,2016) — 시간 제한 환경용')
    a = ap.parse_args()
    link, out = Path(a.link), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cache = Path(a.cache) if a.cache else out / '_중간'; cache.mkdir(parents=True, exist_ok=True)
    y0 = int(a.sgg_start[:4])
    years = sorted(int(p.stem) for p in (link / '일자료_연도별').glob('*.csv') if p.stem.isdigit() and int(p.stem) >= y0)
    if a.years:
        for y in [int(x) for x in a.years.split(',')]: sgg_year(link, y, cache); print('시군구', y, '끝', flush=True)
        return

    # 좌표: 관측소 좌표 평균
    m = pd.read_csv(link / '관측지점_마스터.csv', dtype={'지점': str, '시도': str, '시군구': str}, encoding='utf-8-sig')
    c_sido = m.groupby('시도')[['위도', '경도']].mean().round(4)
    m = norm(m[m['시도'].notna() & m['시군구'].notna()].copy())
    c_sgg = m.groupby(['시도', '시군구'])[['위도', '경도']].mean().round(4)

    # 시도_일
    s = pd.read_csv(link / '시도별_일기상.csv', encoding='utf-8-sig').rename(columns={'지점수_전체': '지점수'})
    s['md'] = s['날짜'].str[5:]
    base = s[(s['날짜'] >= '1991-01-01') & (s['날짜'] <= '2020-12-31')].copy()
    dt_ = pd.to_datetime(base['날짜'])
    norms = []
    for off in range(-3, 4):   # 같은 월·일 ±3일
        t = base[['시도', '평균기온', '최고기온', '최저기온', '강수량']].copy()
        t['md'] = (dt_ - pd.Timedelta(days=off)).dt.strftime('%m-%d').values
        norms.append(t)
    nm = pd.concat(norms).groupby(['시도', 'md']).mean().round(2)
    nm.columns = ['평년_평균기온', '평년_최고기온', '평년_최저기온', '평년_강수량']
    s = s.join(nm, on=['시도', 'md']).join(c_sido, on='시도')
    s['구분'] = '시도_일'; s['시군구'] = ''

    # 시군구_일
    g = pd.concat([sgg_year(link, y, cache) for y in years], ignore_index=True)
    g = g[g['날짜'] >= a.sgg_start].join(c_sgg, on=['시도', '시군구'])
    g['구분'] = '시군구_일'
    for c in ['평년_평균기온', '평년_최고기온', '평년_최저기온', '평년_강수량']: g[c] = np.nan

    D = pd.concat([s, g], ignore_index=True)
    D['값개수'] = D[NV].notna().sum(axis=1)
    n_all = len(D); D = D[D['값개수'] >= 3]
    D = D.sort_values(['구분', '시도', '시군구', '날짜'])[COLS]
    D.to_csv(out / '날씨_대통합_일별.csv', index=False, encoding='utf-8-sig')

    rep = {'만든날': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'), '전체행': len(D), '뺀행(값3개미만)': n_all - len(D)}
    for k, x in D.groupby('구분'):
        rep[k] = {'행': len(x), '기간': [x['날짜'].min(), x['날짜'].max()],
                  '지역수': int(x[['시도', '시군구']].drop_duplicates().shape[0]),
                  '열별_채움률%': {c: round(x[c].notna().mean() * 100, 1) for c in V + ['평년_평균기온', '평년_강수량']}}
    rep['좌표없는_지역'] = D[D['위도'].isna()][['시도', '시군구']].drop_duplicates().values.tolist()
    (out / '점검.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: (v if k != '시군구_일' and k != '시도_일' else {kk: vv for kk, vv in v.items() if kk != '열별_채움률%'}) for k, v in rep.items()}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
