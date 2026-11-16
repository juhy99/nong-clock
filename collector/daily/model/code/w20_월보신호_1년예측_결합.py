# -*- coding: utf-8 -*-
"""70 w20 — 과일(⑦~⑫)·채소(⑮⑯)에서 찾은 '월보 생산 전망 × 탄력'을 628계열 월 단가 1년 예측(w16b 평균판)에 붙여 전체 성적이 좋아지나
- 신호: 기준월 t까지 나온 월보 중, 목표월 m이 속한 시즌(과일) / 작형(채소)의 생산 전망 전년비(마지막 호). 가격 안 씀
  · 과일 사과·배·단감·포도(감귤 제외, ⑧): 재추출 월보(w12a), 시즌 시작 달 ST, 같은 시즌 해 5월호~ t
  · 채소 9품목: 35번 작형별 prod, 작형 시작 8달 전 ~ min(t, 시작 1달 뒤). 가을 감자 달은 고랭지 전망(⑯)
- 탄력: 채소 0.5 × (−1.689)(⑯, 2008~2018로 맞춤), 과일 품목별 b(가락 장기 2018 시즌까지로 맞춤)
- 예측: 평균판(기준) / 평균판+신호 / 작년 같은 달 단가×exp(신호) / 둘 평균(신호 있는 줄만, 없으면 평균판)
- 시험: w16b와 같은 2023 / 2024 / 2025~ 목표월"""
import os, numpy as np, pandas as pd
from pathlib import Path
R = os.environ.get('NC_R', str(Path(__file__).resolve().parents[2]) + '/'); OUTD = Path(os.environ.get('NC_OUT', Path(__file__).resolve().parents[1]))
src = open(Path(__file__).with_name('w18_채소_작형시즌_월보전망_가격.py'), encoding='utf-8').read()
CAL = eval(src[src.index('CAL = {') + 6: src.index('}', src.index('CAL = {')) + 1])
O = pd.read_pickle(OUTD / '_w16b_시험예측.pkl'); O = O.dropna(subset=['lp', '계절']).copy()
P = pd.read_csv(OUTD / '_입력' / '01x_품종월_패널_최대확장.csv.gz', usecols=['계열키', '품목명', '계열']).drop_duplicates('계열키').set_index('계열키')
O = O.join(P, on='계열키'); O['ty'] = O.m // 12; O['tm'] = O.m % 12 + 1
# 채소 월보
W = pd.read_csv(OUTD / '_입력' / '월보_작형별_수급지표_35_05.csv'); W = W[(W.지표 == 'prod') & (W.전년비_pct.abs() <= 80)].copy()
W['mi'] = W.발행.str[:4].astype(int) * 12 + W.발행.str[5:7].astype(int) - 1; W['z'] = np.log1p(W.전년비_pct.clip(-40, 40) / 100)
NM = {'봄': '봄', '고냉지': '고랭지', '여름': '고랭지', '김장(가을': '가을', '가을': '가을', '월동': '겨울', '조생': '조생', '만생': '중만생', '중만생': '중만생', '중생': '중만생'}
Wg = {k: g.sort_values('mi')[['mi', 'z']].values for k, g in W.groupby(['품목', '작형'])}
def veg_z(it, ser, t, m):
    mon = m % 12 + 1; yr = m // 12
    for (i, cr), ms in CAL.items():
        if i != it or mon not in ms: continue
        if ser in NM and NM[ser] != cr: return np.nan
        s = ms[0]; Y = yr if mon >= s else yr - 1; st = Y * 12 + s - 1
        use = '고랭지' if (it == '감자' and cr == '가을') else cr
        if use == '고랭지' and cr == '가을':   # 가을 감자 → 그 해 고랭지 작형 전망
            s2 = CAL[('감자', '고랭지')][0]; st = Y * 12 + s2 - 1
        a = Wg.get((it, use))
        if a is None: return np.nan
        x = a[(a[:, 0] >= st - 8) & (a[:, 0] <= min(t, st + 1))]
        return np.nan if len(x) == 0 else np.median(x[x[:, 0] == x[:, 0].max(), 1])
    return np.nan
# 과일 월보 (감귤 제외)
ST = {'사과': 8, '배': 8, '단감': 7, '포도': 3}
F = pd.read_csv(OUTD / '_입력' / '월보_과일5_생산_재추출.csv'); F = F[(F.지표 == '생산량') & (F.발행월 >= 5) & (F.전년비_pct.abs() <= 60) & F.품목.isin(ST)].copy()
F['mi'] = F.연도 * 12 + F.발행월 - 1; F['z'] = np.log1p(F.전년비_pct / 100); Fg = {k: g[['연도', 'mi', 'z']].values for k, g in F.groupby('품목')}
VV = pd.read_csv(R + '68_시즌단위_과일품종_사과배단감/15_가락장기_2025까지_품종시즌_가격물량.csv').dropna(subset=['dq', 'dp'])
BF = {it: (g.dq * g.dp).sum() / (g.dq ** 2).sum() for it, g in VV[VV.시즌 <= 2018].groupby('품목')}
def fruit_z(it, t, m):
    mon = m % 12 + 1; yr = m // 12; SY = yr if mon >= ST[it] else yr - 1; a = Fg.get(it)
    if a is None: return np.nan
    x = a[(a[:, 0] == SY) & (a[:, 1] <= t)]
    return np.nan if len(x) == 0 else np.median(x[x[:, 1] == x[:, 1].max(), 2])
BV = 0.5 * -1.689
adj = np.full(len(O), np.nan); kind = np.array([''] * len(O), dtype=object)
for i, (it, ser, t, m) in enumerate(zip(O.품목명.values, O.계열.values, O.t.values, O.m.values)):
    if any(k[0] == it for k in CAL):
        z = veg_z(it, ser, t, m)
        if not np.isnan(z): adj[i] = BV * z; kind[i] = '채소'
    elif it in ST:
        z = fruit_z(it, t, m)
        if not np.isnan(z): adj[i] = BF[it] * z; kind[i] = '과일'
O['신호'] = adj; O['종류'] = kind; s = O.신호.notna()
O['평균판'] = O.계절 + O.pd_LGB / 2
O['평균판+신호'] = np.where(s, O.평균판 + O.신호.fillna(0), O.평균판)
O['작년같은달×신호'] = np.where(s & O.ly_lp.notna(), O.ly_lp + O.신호.fillna(0), O.평균판)
O['둘평균'] = np.where(s & O.ly_lp.notna(), (O.평균판 + O.ly_lp + O.신호.fillna(0)) / 2, O.평균판)
O['작년같은달(참고)'] = np.where(s & O.ly_lp.notna(), O.ly_lp, O.평균판)
O['평균판+작년 반반(신호없이·참고)'] = np.where(s & O.ly_lp.notna(), (O.평균판 + O.ly_lp) / 2, O.평균판)   # 둘평균의 이득이 신호 때문인지 확인용
M = ['평균판', '평균판+신호', '작년같은달×신호', '둘평균', '작년같은달(참고)', '평균판+작년 반반(신호없이·참고)']
for c in M: O['e_' + c] = (np.exp(O[c] - O.lp) - 1).abs() * 100
print('줄', len(O), '| 신호 있는 줄', s.sum(), O[s].종류.value_counts().to_dict(), '| 계열', O[s].계열키.nunique())
x = O[s]; print('신호 있는 줄 MAPE', x[['e_' + c for c in M]].mean().round(2).to_dict())
print('종류별'); print(x.groupby('종류')[['e_' + c for c in M]].mean().round(2).to_string())
print('해별(신호 줄)'); print(x.groupby('시험')[['e_' + c for c in M]].mean().round(2).to_string())
k = O.groupby('계열키')[['e_' + c for c in M]].mean(); k.columns = M; print('628계열 전체 계열 중앙', k.median().round(2).to_dict())
rr = np.random.default_rng(0)
for a in ('평균판+신호', '작년같은달×신호', '둘평균'):
    d = (x['e_' + a] - x.e_평균판).dropna().values; bs = [rr.choice(d, len(d)).mean() for _ in range(2000)]
    print(f'  {a} − 평균판(신호 줄)', round(d.mean(), 2), np.percentile(bs, [2.5, 97.5]).round(2))
d = (x['e_둘평균'] - x['e_평균판+작년 반반(신호없이·참고)']).dropna().values; bs = [rr.choice(d, len(d)).mean() for _ in range(2000)]
print('  확인: 둘평균 − 신호 없는 반반 =', round(d.mean(), 2), np.percentile(bs, [2.5, 97.5]).round(2), '(음수면 작년 가격과 섞은 것과 별개로 월보 신호가 더 보탬)')
print('품목별(신호 줄)'); print(x.groupby('품목명')[['e_평균판', 'e_평균판+신호', 'e_평균판+작년 반반(신호없이·참고)']].mean().round(1).to_string())
ks = x.groupby(['품목명', '계열'])[['e_평균판', 'e_평균판+신호']].mean(); ks['이득'] = ks.e_평균판 - ks['e_평균판+신호']
ks['✔'] = ks['이득'].map(lambda v: '✔' if v >= 1 else ('✘' if v <= -1 else '·')); print('계열별 ✔(평균판+신호)', ks['✔'].value_counts().to_dict())
print(ks.round(2).sort_values('이득', ascending=False).to_string())
print('h별(신호 줄)'); print(x.groupby(pd.cut(x.h, [0, 3, 6, 12]))[['e_평균판', 'e_평균판+신호']].mean().round(2).to_string())
ks.round(3).to_csv(OUTD / '24a_월보신호결합_계열별.csv', encoding='utf-8-sig'); x[['계열키', '품목명', '계열', '종류', 't', 'm', 'h', '시험', '신호'] + ['e_' + c for c in M]].round(3).to_csv(OUTD / '24b_월보신호결합_줄.csv.gz', index=False, encoding='utf-8-sig')
