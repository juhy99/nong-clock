# -*- coding: utf-8 -*-
"""원장 일별(품종코드) → 월 패널 다시 만들기 + 새 달 붙이기 (76번 g5와 같은 규칙). 2026-11-13
 tV(322용): 새 정의 코드 묶음 / tW(품목 합침·부모): 구성 26계열의 품종코드
 2020-01부터는 원장 값(국산 금액 ÷ 물량), 2018~19는 예전 값에 물량 배율만 맞춤. 단위 오류 달(단가 < 앞뒤 13달 중앙/8 & 물량 > 8배)은 물량을 고침
 사용: python panel_rebuild.py <원장 일별 csv.gz> <ref 폴더> <tV|tW> <이전 패널 csv.gz> <새 패널 csv.gz> <기준월 YYYY-MM>"""
import sys, numpy as np, pandas as pd
LED, REF, T, PIN, POUT, BASE = sys.argv[1:7]
d = pd.read_csv(LED, dtype={'일자': str, '품목코드4': str, '품종코드': str})
d['c4'] = d.품목코드4.str.zfill(4); d['vc'] = d.품종코드.str.zfill(2); d['연월'] = d.일자.str[:4] + '-' + d.일자.str[4:6]; d = d[d.연월 <= BASE]
MC = d.groupby(['연월', 'c4', 'vc'], as_index=False)[['국산_kg', '국산금액_원']].sum(); MC['code'] = MC.c4 + '-' + MC.vc
MONTHS = sorted(m for m in MC.연월.unique() if m >= '2020-01')
def fix(a):
    a = a.sort_values('연월').reset_index(drop=True); p = a.v / a.q.where(a.q > 0); mp = p.rolling(13, center=True, min_periods=4).median(); mq = a.q.where(a.q > 0).rolling(13, center=True, min_periods=4).median()
    bad = (p < mp / 8) & (a.q > mq * 8); a.loc[bad, 'q'] = a.v[bad] / mp[bad]; a['p'] = np.where(a.q > 0, a.v / a.q, np.nan); return a, int(bad.sum())
if T == 'tV':
    G = pd.read_csv(f'{REF}/단위_계열_새정의.csv').drop_duplicates('새모델계열키').set_index('새모델계열키').new
    TVc = {k: set(v.split(';')) for k, v in G.items() if isinstance(v, str) and v}; codes_of = lambda k: TVc.get(k)
else:
    MP = pd.read_csv(f'{REF}/01_구분매핑표.csv', dtype=str); MP['code'] = MP.품목코드4.str.zfill(4) + '-' + MP.품종코드.str.zfill(2)
    allc = MC[['c4', 'code']].drop_duplicates().merge(MP[['code', '계열키']], on='code', how='left'); allc['계열키'] = allc.계열키.fillna(allc.c4 + '|기타·일반|기타·일반')
    memW = pd.read_csv(f'{REF}/모델계열_구성.csv').drop_duplicates()
    def codes_of(k):
        ks = set(memW[memW.모델계열키 == k].구성_26계열키) or ({k} if '|품종·작형|' in k else set())
        return set(allc[allc.계열키.isin(ks)].code)
P = pd.read_csv(PIN, dtype={'품목코드4': str}); out = []; nfix = 0
for k, g in P.groupby('계열키', sort=False):
    cs = codes_of(k); g = g.sort_values('연월').set_index('연월')
    if not cs: out.append(g.reset_index()); continue
    n = MC[MC.code.isin(cs)].groupby('연월')[['국산_kg', '국산금액_원']].sum()
    ov = g[(g.index >= '2020-01') & (g.index <= '2021-12') & (g.q > 0)].q; sc = (n.국산_kg.reindex(ov.index) / ov).replace([np.inf, -np.inf], np.nan).dropna().median(); sc = sc if np.isfinite(sc) else 1.0
    a = g.reset_index()[['연월', 'q', 'v']].copy()
    add = [m for m in MONTHS if m > a.연월.max()]                      # 새 달 붙이기
    if add: a = pd.concat([a, pd.DataFrame({'연월': add, 'q': 0.0, 'v': np.nan})], ignore_index=True)
    a = a[a.연월 <= BASE]
    old = a.연월 < '2020-01'; a.loc[old, 'q'] = a.loc[old, 'q'] * sc; a.loc[old, 'v'] = a.loc[old, 'v'] * sc
    new = ~old; a.loc[new, 'q'] = a.loc[new, '연월'].map(n.국산_kg).fillna(0.0).values; a.loc[new, 'v'] = a.loc[new, '연월'].map(n.국산금액_원).values
    a.loc[a.q <= 0, 'v'] = np.nan; a, f = fix(a); nfix += f
    meta = g.iloc[0]; a['계열키'] = k
    for c in ('품목코드4', '품목명', '계열', '계열구분'): a[c] = meta[c]
    a['출처'] = np.where(a.연월 < '2020-01', 'aT(물량 배율 맞춤)', '원장품종코드_g3'); out.append(a)
Q = pd.concat(out, ignore_index=True)[P.columns]; Q.to_csv(POUT, index=False, compression='gzip')
print(T, '패널 계열', Q.계열키.nunique(), '| 줄', len(Q), '|', Q.연월.min(), '~', Q.연월.max(), '| 단위 오류 고침', nfix, flush=True)
