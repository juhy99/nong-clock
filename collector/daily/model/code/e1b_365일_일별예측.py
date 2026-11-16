# -*- coding: utf-8 -*-
"""e1 (11-12) 최종 모델(섞기 전: v4 + 품목 따라가기 + 반반, 일·주 u7c)로 365일 일별 예측
 - 1~14거래일: u7c 일 예측(새기준) 그대로. 그 뒤 10거래일은 두 값의 차이를 줄여 이음
 - 그 뒤 ~ 12달(2027-10): 그 달 월 예측(01 파일) × 달 안 날짜 모양
     날짜 모양 = 과거 일별 log 단가에서 (그날 − 그 해 그 달 평균)의 평균: ISO 주 + 요일. 달마다 평균 0으로 맞춤 → 달 평균 = 월 예측
 - 13번째 달(2027-11-01~11-10): v4가 12달까지라 평년(같은 달 평균) × (마지막 예측 달의 v4 ÷ 평년) — 참고 값
 - 출하철 밖 달은 비움(1~14거래일 u7c 값은 남기고 출하철 표시). 월~토만(일요일 휴장)
 - 시험: 2025-01~2026-09 목표월 시험 줄의 월 예측 × 모양을 그 달 실제 일별 단가로 채점 (모양은 시험 해 전 자료로만)
 사용: python e1_365일_일별예측.py <묶음 폴더> <출력 폴더>"""
import sys, os, numpy as np, pandas as pd
K, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
D = pd.read_csv(f'{K}/데이터/02_322단위_일별가격_20200101_20261110.csv.gz', parse_dates=['date']).rename(columns={'세부단위': '예측단위'})
D = D[D.단가_원kg > 0].copy(); D['lp'] = np.log(D.단가_원kg); D['y'] = D.date.dt.year; D['m'] = D.date.dt.month
D['wk'] = D.date.dt.isocalendar().week.clip(upper=52).astype(int); D['wd'] = D.date.dt.dayofweek
D['dev'] = D.lp - D.groupby(['예측단위', 'y', 'm']).lp.transform('mean')
def shape_tables(before):
    x = D[D.date < before]
    sw = x.groupby(['예측단위', 'm', 'wk']).dev.mean()
    r = x.dev - x.set_index(['예측단위', 'm', 'wk']).index.map(sw).values
    sd = pd.Series(r.values, index=x.index).groupby([x.예측단위, x.wd]).mean()
    return sw, sd
def apply_shape(df, sw, sd):   # df: 예측단위, date, 월키(그룹) → s (그룹 평균 0)
    m = df.date.dt.month; wk = df.date.dt.isocalendar().week.clip(upper=52).astype(int); wd = df.date.dt.dayofweek
    a = pd.Series(list(zip(df.예측단위, m, wk))).map(sw).fillna(0).values + pd.Series(list(zip(df.예측단위, wd))).map(sd).fillna(0).values
    df = df.assign(s_raw=a); df['s'] = df.s_raw - df.groupby(['예측단위', '월키']).s_raw.transform('mean'); return df
W = D.groupby(['예측단위', D.date.dt.isocalendar().year.rename('iy'), 'wk']).lp.mean()   # 작년 같은 주(비교용)

# ===== 1) 시험: 2025-01~2026-09 =====
T = pd.read_csv(f'{K}/결과_기준202610/02_322_월예측_시험줄_2023부터.csv.gz')
T = T[(T.출하철 == 1) & (T.목표월 >= '2025-01') & (T.목표월 <= '2026-09')].dropna(subset=['예측_원kg'])
res = []
for Y in (2025, 2026):
    sw, sd = shape_tables(pd.Timestamp(f'{Y}-01-01'))
    t = T[T.목표월.str[:4] == str(Y)][['예측단위', '기준월', '목표월', 'h', '예측_원kg']]
    a = D[D.y == Y][['예측단위', 'date', 'lp']].assign(목표월=lambda x: x.date.dt.strftime('%Y-%m'))
    z = t.merge(a, on=['예측단위', '목표월']); z['월키'] = z.기준월 + '|' + z.목표월
    z = apply_shape(z, sw, sd)
    z['p_모양'] = np.log(z.예측_원kg) + z.s; z['p_평평'] = np.log(z.예측_원kg)
    iso = z.date.dt.isocalendar(); z['p_작년주'] = pd.Series(list(zip(z.예측단위, iso.year - 1, iso.week.clip(upper=52)))).map(W).values
    z['일수'] = (z.date - (pd.PeriodIndex(z.기준월, freq='M').end_time.normalize())).dt.days
    res.append(z)
Z = pd.concat(res).dropna(subset=['p_작년주'])
Z['구간'] = pd.cut(Z.일수, [0, 30, 90, 180, 270, 400], labels=['1~30일', '31~90일', '91~180일', '181~270일', '271~365일'])
def acc(x, c):
    e = (np.exp(x[c] - x.lp) - 1).abs().groupby(x.예측단위).mean() * 100; return round(100 - e.median(), 1)
rows = []
for (g, y), x in Z.groupby(['구간', Z.date.dt.year], observed=True):
    rows.append(dict(구간=g, 해=y, 단위=x.예측단위.nunique(), 줄=len(x), 월예측x모양=acc(x, 'p_모양'), 월예측_평평=acc(x, 'p_평평'), 작년같은주=acc(x, 'p_작년주')))
for y, x in Z.groupby(Z.date.dt.year):
    rows.append(dict(구간='전체', 해=y, 단위=x.예측단위.nunique(), 줄=len(x), 월예측x모양=acc(x, 'p_모양'), 월예측_평평=acc(x, 'p_평평'), 작년같은주=acc(x, 'p_작년주')))
S = pd.DataFrame(rows); S.to_csv(f'{OUT}/02_365일_일별_시험성적.csv', index=False, encoding='utf-8-sig'); print(S.to_string(index=False), flush=True)

# ===== 2) 앞으로 365일 (기준일 = 일별 자료 마지막 날) =====
base = D.date.max(); days = pd.date_range(base + pd.Timedelta(days=1), base + pd.Timedelta(days=365)); days = days[days.dayofweek < 6]
F = pd.read_csv(f'{K}/결과_기준202610/01_322_월예측_기준202610_앞으로12달.csv')
U = F.drop_duplicates('예측단위')[['예측단위', '품목', '묶음', '모델', '출하철' if False else '예측단위']].iloc[:, :4]
SS = pd.read_csv(f'{K}/데이터/05_322단위표_모델계열_부모_모델_출하철.csv').set_index('예측단위').출하철.map(lambda s: set(map(int, str(s).split(','))))
sw, sd = shape_tables(base + pd.Timedelta(days=1))
G = pd.DataFrame([(u, d) for u in U.예측단위 for d in days], columns=['예측단위', 'date']); G['목표월'] = G.date.dt.strftime('%Y-%m'); G['월키'] = G.목표월
G = apply_shape(G, sw, sd)
G = G.merge(F[['예측단위', '목표월', '예측_원kg', '하한10', '상한90', '작년같은달_원kg']], on=['예측단위', '목표월'], how='left')
G['출하철'] = [int(d.month in SS[u]) for u, d in zip(G.예측단위, G.date)]
G['방법'] = np.where(G.예측_원kg.notna(), '월 예측 × 날짜 모양', '')
G['예측'] = G.예측_원kg * np.exp(G.s); G['하한'] = G.하한10 * np.exp(G.s); G['상한'] = G.상한90 * np.exp(G.s)
# 13번째 달: 평년 × 마지막 예측 달 비율
P = pd.read_csv(f'{K}/데이터/03_322단위_월가격_모델패널_201801_202610.csv.gz'); P = P[P.단가_원kg > 0]
PN = P.assign(달=P.연월.str[5:].astype(int)).groupby(['예측단위', '달']).단가_원kg.apply(lambda s: np.exp(np.log(s).mean()))
last = F.dropna(subset=['예측_원kg']).sort_values('목표월').groupby('예측단위').last()
ext = (G.예측_원kg.isna()) & (G.목표월 > F.목표월.max()) & (G.출하철 == 1)
for i in G.index[ext]:
    u = G.at[i, '예측단위']
    if u not in last.index: continue
    r = last.at[u, '예측_원kg'] / PN.get((u, int(last.at[u, '목표월'][5:])), np.nan); pn = PN.get((u, G.at[i, 'date'].month), np.nan)
    if np.isfinite(r) and np.isfinite(pn): G.at[i, '예측'] = pn * r * np.exp(G.at[i, 's']); G.at[i, '방법'] = '13번째 달: 평년 × 마지막 예측 달 비율(참고)'
G.loc[G.출하철 == 0, ['예측', '하한', '상한']] = np.nan; G.loc[G.출하철 == 0, '방법'] = ''
# 1~14거래일: u7c (만감 4단위는 월 예측과 같게 감귤 쪽 계열)
M4 = {'만감 레드향': '감귤 레드향', '만감 황금향': '감귤 황금향', '만감 카라향': '감귤 카라향', '만감 천혜향': '감귤 천혜향'}
d7 = pd.read_csv(f'{K}/결과_기준202610/05_일별예측_기준20261110_1to14거래일.csv', parse_dates=['목표일'])
if d7.단위.isin(M4.values()).any(): d7 = d7[~d7.단위.isin(M4)]; d7['예측단위'] = d7.단위.map({v: k for k, v in M4.items()}).fillna(d7.단위)   # 326 이름일 때만
else: d7['예측단위'] = d7.단위   # 322 이름(u7d)
d7 = d7[d7.예측단위.isin(U.예측단위)].set_index(['예측단위', '목표일']).새기준_원kg
k7 = pd.Series(list(zip(G.예측단위, G.date))).map(d7).values; use = ~np.isnan(k7)
G['_월값'] = G.예측; G.loc[use, '예측'] = k7[use]; G.loc[use, ['하한', '상한']] = np.nan; G.loc[use, '방법'] = '1~14거래일: 일 모델(u7d)'
# 이음: 14거래일째에 일 모델과 월 예측×모양이 다르면, 그 차이(log)를 다음 10거래일에 걸쳐 0으로 줄임 (값이 갑자기 뛰지 않게)
G = G.sort_values(['예측단위', 'date']).reset_index(drop=True)
for u, g in G.groupby('예측단위'):
    i7 = g.index[g.방법 == '1~14거래일: 일 모델(u7d)']
    if not len(i7): continue
    l = i7.max()
    if not (np.isfinite(G.at[l, '_월값']) and np.isfinite(G.at[l, '예측'])): continue
    k = np.log(G.at[l, '예측'] / G.at[l, '_월값'])
    for n, i in enumerate(range(l + 1, min(l + 11, g.index.max() + 1)), 1):
        if not np.isfinite(G.at[i, '예측']) or G.at[i, '방법'] != '월 예측 × 날짜 모양': break
        f = np.exp(k * (1 - n / 10)); G.loc[i, ['예측', '하한', '상한']] = G.loc[i, ['예측', '하한', '상한']].values * f
        if n < 10: G.at[i, '방법'] = '월 예측 × 날짜 모양 (일 모델에서 이어지는 10거래일)'
G['일수'] = (G.date - base).dt.days; G['기준일'] = base.strftime('%Y-%m-%d'); G['날짜'] = G.date.dt.strftime('%Y-%m-%d')
G = G.merge(U[['예측단위', '품목', '묶음', '모델']], on='예측단위', how='left')
out = G[['예측단위', '품목', '묶음', '모델', '기준일', '날짜', '일수', '출하철', '방법', '예측', '하한', '상한', '작년같은달_원kg']].rename(columns={'예측': '예측_원kg', '하한': '하한10_원kg', '상한': '상한90_원kg', '모델': '월모델'})
out.round(0).to_csv(f'{OUT}/01_322_365일_일별예측_기준{base:%Y%m%d}.csv.gz', index=False, compression='gzip')
print('앞으로', base.date(), '→', days.max().date(), '| 단위', out.예측단위.nunique(), '| 줄', len(out), '| 예측 있는 줄', int(out.예측_원kg.notna().sum()), flush=True)
print(out.groupby('방법').size().to_dict())
