# -*- coding: utf-8 -*-
"""70 w18 — 채소 9품목(배추·무·양배추·당근·감자·양파·마늘·대파·건고추)을 작형 단위 시즌으로 나눠, 관측월보 작형별 생산 전망 × 탄력으로 가격을 맞히나 (2008~2022)
- 물량·가격: 45번 가락 거래연보 품목 월 반입 / 품종·규격·등급 월 가격(같은 줄끼리 로그 차이 중앙). 단가는 정답으로만
- 작형 출하 달: 일반 재배력 기준 가정(아래 CAL). 작형 해 = 출하 시작 달의 연도
- 월보 전망: 35번 05 통합(prod = 생산량 전년비 %), 그 작형의 출하 시작 8달 전 ~ 시작 1달 뒤 발행 중 기준 시점까지 마지막 호
- 방법: 지난 작형 그대로 / 탄력 × 월보(시작 전) / 탄력 × 월보(시작 뒤 1달까지) / 탄력 × 실제 물량(상한). b는 그 해 전 작형-해로 맞춤(절편 없음, 6개 이상)"""
import os, numpy as np, pandas as pd
from pathlib import Path
R = os.environ.get('NC_R', str(Path(__file__).resolve().parents[2]) + '/'); OUTD = Path(os.environ.get('NC_OUT', Path(__file__).resolve().parents[1]))
D45 = R + '00_기본자료/02_전처리/45_가락거래연보_반입량가격_2000_2022/'
_w = OUTD / '_입력' / '월보_작형별_수급지표_35_05.csv'   # 35번 05 통합 사본(원본: 03_추가자료작업/35_관측월보_작형별_수급지표)
W = pd.read_csv(_w if _w.exists() else R + '03_추가자료작업_01/추가자료작업/35_관측월보_작형별_수급지표/05_통합_품목_작형_지표_발행월_전년비.csv')
W = W[(W.지표 == 'prod') & (W.전년비_pct.abs() <= 80)].copy(); W['mi'] = W.발행.str[:4].astype(int) * 12 + W.발행.str[5:7].astype(int) - 1
CAL = {('배추', '봄'): [5, 6], ('배추', '고랭지'): [7, 8, 9, 10], ('배추', '가을'): [11, 12], ('배추', '겨울'): [1, 2, 3, 4],
       ('무', '봄'): [5, 6], ('무', '고랭지'): [7, 8, 9, 10], ('무', '가을'): [11, 12], ('무', '겨울'): [1, 2, 3, 4],
       ('양배추', '봄'): [4, 5, 6], ('양배추', '고랭지'): [7, 8, 9, 10], ('양배추', '가을'): [11, 12], ('양배추', '겨울'): [1, 2, 3],
       ('당근', '봄'): [6, 7], ('당근', '고랭지'): [8, 9, 10], ('당근', '가을'): [11, 12], ('당근', '겨울'): [1, 2, 3, 4, 5],
       ('감자', '봄'): [6, 7, 8], ('감자', '고랭지'): [9, 10, 11], ('감자', '가을'): [12, 1, 2],
       ('양파', '조생'): [4, 5], ('양파', '중만생'): [6, 7, 8, 9, 10, 11, 12, 1, 2, 3],
       ('마늘', '전체'): [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5], ('대파', '전체'): list(range(1, 13)), ('건고추', '전체'): [9, 10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8]}
A = pd.read_csv(D45 + '01_가락_품목_월별반입_2000_2022.csv').groupby(['품목', '연도', '월']).반입_t.sum()
B = pd.read_csv(D45 + '03_가락_품종규격별_월거래가격_2002_2022.csv'); B = B[B.가격_원 > 0]
B['줄'] = B.품목품종.fillna('') + '|' + B.규격.astype(str) + '|' + B.단위.fillna('') + '|' + B.등급.fillna('없음')
B = B.groupby(['품목', '줄', '연도', '월']).가격_원.mean().pipe(np.log).rename('lp').reset_index()
rows = []
for (it, cr), ms in CAL.items():
    s = ms[0]
    for Y in range(2000, 2023):
        mons = [(Y + (1 if (m < s) else 0), m) for m in ms]           # 시작 달보다 작은 달은 다음 해
        q = [A.get((it, y, m), np.nan) for y, m in mons]
        if any(pd.isna(q)) or mons[-1][0] > 2022: continue
        b = B[(B.품목 == it) & B.set_index(['연도', '월']).index.isin(mons)]
        lp = b.groupby('줄').agg(lp=('lp', 'mean'), n=('lp', 'size')); lp = lp[lp.n >= max(1, len(ms) // 2)]
        st = Y * 12 + s - 1
        w = W[(W.품목 == it) & (W.작형 == cr) & (W.mi >= st - 8) & (W.mi <= st + 1)]
        f0 = w[w.mi <= st - 1]; f1 = w
        last = lambda x: np.nan if x.empty else x[x.mi == x.mi.max()].전년비_pct.median()
        rows.append({'품목': it, '작형': cr, '해': Y, 'q': sum(q), '줄lp': lp.lp.to_dict(), '월보_시작전': last(f0), '월보_시작후1달': last(f1)})
T = pd.DataFrame(rows).sort_values(['품목', '작형', '해'])
out = []
for (it, cr), g in T.groupby(['품목', '작형']):
    g = g.reset_index(drop=True); g['dq'] = np.log(g.q).diff()
    dp = [np.nan] + [np.median([v - g.줄lp[i - 1][k] for k, v in g.줄lp[i].items() if k in g.줄lp[i - 1]]) if (g.해[i] - g.해[i - 1] == 1 and set(g.줄lp[i]) & set(g.줄lp[i - 1])) else np.nan for i in range(1, len(g))]
    g['dp'] = dp; g = g.dropna(subset=['dq', 'dp'])
    for _, r in g[g.해 >= 2008].iterrows():
        tr = g[g.해 < r.해]
        if len(tr) < 6: continue
        b = (tr.dq * tr.dp).sum() / (tr.dq ** 2).sum(); f = lambda z: abs(np.exp(z - r.dp) - 1) * 100
        z0 = np.log1p(r.월보_시작전 / 100) if pd.notna(r.월보_시작전) else 0; z1 = np.log1p(r.월보_시작후1달 / 100) if pd.notna(r.월보_시작후1달) else 0
        out.append({'품목': it, '작형': cr, '해': r.해, 'b': b, 'dq': r.dq, 'dp': r.dp, '월보있음': pd.notna(r.월보_시작후1달), '월보_시작후1달_pct': r.월보_시작후1달,
                    '그대로': f(0), '탄력×월보(시작전)': f(b * z0), '탄력×월보(시작후1달)': f(b * z1), '탄력×실제(상한)': f(b * r.dq)})
D = pd.DataFrame(out); c = ['그대로', '탄력×월보(시작전)', '탄력×월보(시작후1달)', '탄력×실제(상한)']
pd.set_option('display.width', 250); print('작형-해', len(D), '| 월보 있는 비율 %', round(D.월보있음.mean() * 100, 1)); print(D[c].mean().round(2).to_dict())
G = D.groupby(['품목', '작형']).agg(n=('해', 'size'), 월보n=('월보있음', 'sum'), b=('b', 'last'), **{k: (k, 'mean') for k in c}).reset_index()
G['월보이득'] = G.그대로 - G['탄력×월보(시작후1달)']; G['상한이득'] = G.그대로 - G['탄력×실제(상한)']
mk = lambda x: '✔' if x >= 1 else ('✘' if x <= -1 else '·'); G['월보✔'] = G.월보이득.map(mk); G['상한✔'] = G.상한이득.map(mk)
print(G.round(2).sort_values('상한이득', ascending=False).to_string(index=False))
x = D[D.월보있음]; print('월보 있는 작형-해', len(x), x[c].mean().round(2).to_dict()); print('월보 전망 ~ 실제 반입 상관', round(np.corrcoef(np.log1p(x.월보_시작후1달_pct / 100), x.dq)[0, 1], 3))
rr = np.random.default_rng(0); d = (D['탄력×월보(시작후1달)'] - D.그대로).values; bs = [rr.choice(d, len(d)).mean() for _ in range(3000)]; print('월보(시작후1달) − 그대로', round(d.mean(), 2), np.percentile(bs, [2.5, 97.5]).round(2))
G.round(3).to_csv(OUTD / '22a_채소_작형시즌_월보탄력_요약.csv', index=False, encoding='utf-8-sig'); D.round(4).to_csv(OUTD / '22b_채소_작형시즌_월보탄력_해별.csv', index=False, encoding='utf-8-sig')
# ---- 2단계: 가락 반입 대신 '월보 생산 전망 → 가격'을 바로 맞춤 (가락 반입이 공급을 못 나타냄: 배추·무는 반입↑일 때 값도↑) ----
D['z0'] = np.log1p(D['월보_시작후1달_pct'].clip(-40, 40) / 100)   # ±40% 넘는 값은 글자 인식 오류 가능 → 자름
print('상관 월보z~dp', round(D[['z0', 'dp']].dropna().corr().iloc[0, 1], 3), '| 가락 dq~dp', round(D[['dq', 'dp']].corr().iloc[0, 1], 3), '| 월보z~가락dq', round(D[['z0', 'dq']].dropna().corr().iloc[0, 1], 3))
print(D.groupby('품목').apply(lambda g: pd.Series({'월보z~dp': g[['z0', 'dp']].dropna().corr().iloc[0, 1], '가락dq~dp': g[['dq', 'dp']].corr().iloc[0, 1], '월보z~가락dq': g[['z0', 'dq']].dropna().corr().iloc[0, 1], 'n': g.z0.notna().sum()})).round(2).to_string())
o2 = []
for _, r in D.iterrows():
    f = lambda z: abs(np.exp(z - r.dp) - 1) * 100; z = 0 if pd.isna(r.z0) else r.z0
    res = {'품목': r.품목, '작형': r.작형, '해': r.해, '월보있음': pd.notna(r.z0), '그대로': f(0)}
    for nm, pool, k in (('작형b', D[(D.품목 == r.품목) & (D.작형 == r.작형)], 1.0), ('품목b', D[D.품목 == r.품목], 1.0), ('채소공통b', D, 1.0), ('채소공통b절반', D, 0.5)):
        tr = pool[(pool.해 < r.해)].dropna(subset=['z0'])
        bz = min(0.0, (tr.z0 * tr.dp).sum() / (tr.z0 ** 2).sum()) if len(tr) >= 5 else 0.0     # 음수만(공급↑ → 값↓)
        res['탄력(월보)×월보·' + nm] = f(k * bz * z); res['b_' + nm] = bz
    o2.append(res)
E = pd.DataFrame(o2); cc = ['그대로', '탄력(월보)×월보·작형b', '탄력(월보)×월보·품목b', '탄력(월보)×월보·채소공통b', '탄력(월보)×월보·채소공통b절반']
print('작형-해', len(E), E[cc].mean().round(2).to_dict()); x = E[E.월보있음]; print('월보 있는', len(x), x[cc].mean().round(2).to_dict())
for a in cc[1:]:
    d = (E[a] - E.그대로).values; bs = [rr.choice(d, len(d)).mean() for _ in range(3000)]; print(' ', a, '− 그대로', round(d.mean(), 2), np.percentile(bs, [2.5, 97.5]).round(2))
H = E.groupby(['품목', '작형']).agg(n=('해', 'size'), 월보n=('월보있음', 'sum'), **{k: (k, 'mean') for k in cc}).reset_index()
H['이득(공통b절반)'] = H.그대로 - H['탄력(월보)×월보·채소공통b절반']; H['✔'] = H['이득(공통b절반)'].map(mk)
print(H.round(2).sort_values('이득(공통b절반)', ascending=False).to_string(index=False)); print('✔', (H['✔'] == '✔').sum(), '·', (H['✔'] == '·').sum(), '✘', (H['✔'] == '✘').sum())
print('해별', E.groupby('해')[['그대로', '탄력(월보)×월보·채소공통b절반']].mean().round(1).T.to_string())
print('채소공통 b(마지막 해 학습분)', round(E[E.해 == E.해.max()].b_채소공통b.iloc[0], 3))
H.round(3).to_csv(OUTD / '22c_채소_작형_월보직접탄력_요약.csv', index=False, encoding='utf-8-sig'); E.round(4).to_csv(OUTD / '22d_채소_작형_월보직접탄력_해별.csv', index=False, encoding='utf-8-sig')
