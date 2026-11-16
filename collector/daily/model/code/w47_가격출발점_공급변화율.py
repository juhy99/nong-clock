# -*- coding: utf-8 -*-
"""70 w47 (11-04) 새 기준: 가격은 '어디서 출발하나'만, '얼마나 오르내리나'는 공급 자료로만
 예측 가격 = 출발 가격(작년 같은 달 그 품종 원장 단가) × exp(공급 변화율)
   공급 변화율 = LightGBM(목표: log 단가 − log 작년 같은 달 단가, 입력: 17변수 = 출하·면적·품목물량·월보 생산 전망 신호·달력·품목. 가격 0칸)
 섞기: 위 예측과 가격 없는 평균판(계절평균 + 가격없는 LGB 편차 절반)을 log 공간에서 w : (1−w). w 는 시험 해 바로 전 해(검증 해)로만 고름
 가격 흐름(지난달·최근 3달 가격) 변수는 넣지 않음. 출발 가격 1개(1년 전 수준)만 씀
 분해: 평균판(가격 없음) → 작년 가격 그대로 → 작년×공급 LGB(월보 신호 뺌) → 작년×공급 LGB(월보 신호 포함) → 섞기
 시험 2023 / 2024 / 2025~ (학습은 그 해 1월 전 목표월만). 마지막에 기준월(최신) 1~12달 예측표 + 80% 구간(검증 해 잔차 분위)"""
import os, sys, time, numpy as np, pandas as pd, lightgbm as lgb, warnings; warnings.filterwarnings('ignore')
from pathlib import Path
os.environ.setdefault('NC_FEAT', 'dropsig')
src = open(Path(__file__).with_name('w23_변수세트_비교.py'), encoding='utf-8').read()
exec(src[:src.index('def num(x, med)')])
OUT2 = OUTD / '50_새기준_가격출발점'; OUT2.mkdir(exist_ok=True)
F_ns = [c for c in F if c != '월보신호']
PRw = PR   # 품종 log 단가 (계열 × 달)
D['lp_t'] = PRw[D.kid.values, D.t.values - T0]          # 기준월 단가: 평가(방향)용만, 입력 아님
assert '월보신호' in F and not any(c in F for c in ('lp', 'ly_lp', 'lp_t'))

# ---- 월보 생산 전망 × 탄력 b (w20과 같은 규칙: 채소 작형 0.5×(−1.689), 과일 품목 b는 2018 시즌까지로 맞춤). 가격 안 씀
_w20 = open(Path(__file__).with_name('w20_월보신호_1년예측_결합.py'), encoding='utf-8').read()
_s = _w20[_w20.index("src = open(Path(__file__).with_name('w18"):_w20.index('BV = 0.5 * -1.689')]
_s = _s.replace("O = pd.read_pickle(OUTD / '_w16b_시험예측.pkl'); O = O.dropna(subset=['lp', '계절']).copy()\n", '')
_s = _s[:_s.index('P = pd.read_csv(OUTD')] + _s[_s.index('O = O.join(P, on=\'계열키\'); O[\'ty\'] = O.m // 12; O[\'tm\'] = O.m % 12 + 1') + len("O = O.join(P, on='계열키'); O['ty'] = O.m // 12; O['tm'] = O.m % 12 + 1"):]
_F_save = F; exec(_s); WF_ = F; F = _F_save; BV = 0.5 * -1.689
_PI = pd.read_csv(OUTD / '_입력' / '01x_품종월_패널_최대확장.csv.gz', usecols=['계열키', '품목명', '계열']).drop_duplicates('계열키').set_index('계열키')
_u = D[['계열키', 't', 'm']].drop_duplicates().join(_PI, on='계열키'); adj = []
for it, ser, t_, m_ in zip(_u.품목명.values, _u.계열.values, _u.t.values, _u.m.values):
    a_ = np.nan
    if any(k_[0] == it for k_ in CAL):
        z_ = veg_z(it, ser, t_, m_); a_ = BV * z_ if not np.isnan(z_) else np.nan
    elif it in ST:
        z_ = fruit_z(it, t_, m_); a_ = BF[it] * z_ if not np.isnan(z_) else np.nan
    adj.append(a_)
_u['월보adj'] = adj; D = D.merge(_u[['계열키', 't', 'm', '월보adj']], on=['계열키', 't', 'm'], how='left')
print('월보×b 있는 줄', int(D.월보adj.notna().sum()), '계열', D.loc[D.월보adj.notna(), '계열키'].nunique(), flush=True)
def lgbr(tr, y, F_, w=None, seed=0):
    return lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=50, subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
                             objective='l1', random_state=seed, verbose=-1).fit(tr[F_], y, sample_weight=w)
def season(trp_mi, rows):
    trp = P[P.mi < trp_mi].dropna(subset=['lp']).assign(달=lambda x: x.mi % 12 + 1)
    S = trp.groupby(['kid', '달']).lp.mean(); Sk = trp.groupby('kid').lp.mean()
    s = pd.Series([S.get((k, mm), np.nan) for k, mm in zip(rows.kid, rows.목표달)], index=rows.index)
    return s.fillna(rows.kid.map(Sk))
def fit_predict(cut, te):
    """cut(목표월 mi) 전 줄로 학습 → te 예측. 반환: 계절, pf(가격없음 편차), chg(변화율), chg_ns(월보 뺀 변화율)"""
    tr = D[D.m < cut].copy(); tr['계절'] = season(cut, tr); te = te.copy(); te['계절'] = season(cut, te)
    b = tr.dropna(subset=['lp', '계절']); te['pf'] = lgbr(b, b.lp - b.계절, F).predict(te[F])
    c = tr.dropna(subset=['lp', 'ly_lp']); c = c[(c.lp - c.ly_lp).abs() < 2.5]
    te['chg'] = lgbr(c, c.lp - c.ly_lp, F).predict(te[F]); te['chg_ns'] = lgbr(c, c.lp - c.ly_lp, F_ns).predict(te[F_ns])
    return te
HALF = float(os.environ.get('NC_HALF', '1.0'))
def forms(x, w):
    x = x.copy()
    x['f_평균판'] = x.계절 + x.pf / 2
    x['f_작년그대로'] = x.ly_lp
    x['f_작년x공급_월보뺌'] = x.ly_lp + x.chg_ns
    x['f_작년x공급'] = x.ly_lp + x.chg
    x['f_작년반반'] = 0.5 * x.ly_lp + 0.5 * x.f_평균판                 # w20 '가격 보조(작년 가격 반반)'과 같은 식
    x['f_작년x월보'] = x.ly_lp + x.월보adj.fillna(0)
    x['f_가격없음LGB'] = x.계절 + HALF * x.pf      # w49 모델 비교: 편차를 다 쓰는 LightGBM(HALF=1)이 섞기에서 가장 좋음(−0.19 [−0.33, −0.05])
    x['f_섞기'] = np.where(x.ly_lp.notna(), w * x.f_작년x월보 + (1 - w) * x.f_가격없음LGB, x.f_가격없음LGB)
    return x
FORMS = ['f_평균판', 'f_가격없음LGB', 'f_작년그대로', 'f_작년반반', 'f_작년x월보', 'f_작년x공급_월보뺌', 'f_작년x공급', 'f_섞기']
def ape(x, c): return (np.exp(x[c] - x.lp) - 1).abs() * 100
out, wsel, qs = [], {}, {}
for Y in (2023, 2024, 2025):
    t0 = time.time(); s0 = Y * 12; e0 = (Y + 1) * 12 if Y < 2025 else 10**9
    # 검증 해(Y−1)로 w 고르기 + 잔차 분위(구간)
    va = fit_predict(s0 - 12, D[(D.m >= s0 - 12) & (D.m < s0)].dropna(subset=['lp']))
    best = None
    for w in np.round(np.arange(0, 1.01, 0.1), 1):
        v = forms(va, w); v = v.dropna(subset=['ly_lp']); e = ape(v, 'f_섞기').groupby(v.계열키).mean().median()
        if best is None or e < best[1]: best = (w, e)
    wsel[Y] = best[0]; v = forms(va, best[0]); r = (v.lp - v.f_섞기).dropna()
    qs[Y] = v.assign(r=v.lp - v.f_섞기).groupby('h').r.quantile([0.1, 0.9]).unstack()
    te = fit_predict(s0, D[(D.m >= s0) & (D.m < e0)].dropna(subset=['lp']))
    te = forms(te, wsel[Y]); te['시험'] = f'{Y}' if Y < 2025 else '2025~'
    te = te.join(qs[Y].rename(columns={0.1: 'q10', 0.9: 'q90'}), on='h')
    out.append(te[['계열키', 'kid', 't', 'h', 'm', 'lp', 'ly_lp', 'lp_t', '계절', 'pf', 'chg', 'chg_ns', '월보adj', 'q10', 'q90', '시험'] + FORMS])
    print(Y, 'w(작년x공급 쪽)', wsel[Y], '검증 중앙', round(best[1], 2), '| 시험 줄', len(te), round(time.time() - t0), '초', flush=True)
O = pd.concat(out); O.to_pickle(OUT2 / '_w47_시험예측.pkl')
# ---- 성적: 계열 중앙 MAPE, 같은 줄(작년 단가 있는 줄)끼리
A = O.dropna(subset=['ly_lp']).copy()
for c in FORMS: A['e_' + c] = ape(A, c)
rows = []
for nm, g in [('전체', A)] + [(y, A[A.시험 == y]) for y in ('2023', '2024', '2025~')]:
    k = g.groupby('계열키')[['e_' + c for c in FORMS]].mean()
    rows.append({'범위': nm, '계열': len(k), **{c[2:]: round(k['e_' + c].median(), 2) for c in FORMS}})
T = pd.DataFrame(rows); print(T.to_string(index=False)); T.to_csv(OUT2 / '01_분해_성적.csv', index=False, encoding='utf-8-sig')
# 차이 신뢰구간 (계열 붓스트랩)
rng = np.random.default_rng(0); k = A.groupby('계열키')[['e_' + c for c in FORMS]].mean(); ci = []
for a_, b_ in [('f_가격없음LGB', 'f_섞기'), ('f_작년반반', 'f_작년x월보'), ('f_평균판', 'f_작년반반'), ('f_평균판', 'f_작년x공급'), ('f_작년반반', 'f_작년x공급'), ('f_작년x공급_월보뺌', 'f_작년x공급'), ('f_평균판', 'f_섞기'), ('f_작년그대로', 'f_섞기'), ('f_작년반반', 'f_섞기')]:
    d = (k['e_' + b_] - k['e_' + a_]).clip(-100, 100).dropna().values; bs = np.percentile([rng.choice(d, len(d)).mean() for _ in range(2000)], [2.5, 97.5])
    ci.append({'기준': a_[2:], '비교': b_[2:], '계열평균차': round(d.mean(), 2), '95%낮음': round(bs[0], 2), '95%높음': round(bs[1], 2), '나은계열%': round((d < 0).mean() * 100, 1)})
C = pd.DataFrame(ci); print(C.to_string(index=False)); C.to_csv(OUT2 / '02_차이_신뢰구간.csv', index=False, encoding='utf-8-sig')
# 지평별 + 방향(기준월 단가 대비) + 구간 포함
A['dir_ok'] = np.sign(A.f_섞기 - A.lp_t) == np.sign(A.lp - A.lp_t); A['in80'] = (A.lp >= A.f_섞기 + A.q10) & (A.lp <= A.f_섞기 + A.q90)
H = A.groupby('h').apply(lambda g: pd.Series({'섞기': g.groupby('계열키').e_f_섞기.mean().median(), '평균판': g.groupby('계열키').e_f_평균판.mean().median(),
     '작년그대로': g.groupby('계열키').e_f_작년그대로.mean().median(), '방향적중%': g.dropna(subset=['lp_t']).dir_ok.mean() * 100, '80%구간포함%': g.in80.mean() * 100})).round(2)
print(H.to_string()); H.to_csv(OUT2 / '03_지평별_방향_구간.csv', encoding='utf-8-sig')
k.median().round(2).to_csv(OUT2 / '01b_계열중앙.csv', encoding='utf-8-sig')
pd.Series(wsel).to_csv(OUT2 / '04_섞기비율_w.csv', encoding='utf-8-sig')
# 계열별 성적
S = A.groupby('계열키')[['e_' + c for c in FORMS]].mean().round(2); S.columns = [c[4:] for c in S.columns]
S.join(P.drop_duplicates('계열키').set_index('계열키')[['품목명', '계열']] if '품목명' in P else None).to_csv(OUT2 / '05_계열별_성적.csv', encoding='utf-8-sig')
print('w', wsel)
# ======== 최신 기준월 1~12달 예측표 (학습 = 정답 있는 모든 줄), w = 마지막 검증(2025~) 값, 80% 구간 = 2025~ 검증 잔차 분위
tl = D.t.max(); cut = tl + 1
tr = D[D.m < cut].copy(); tr['계절'] = season(cut, tr); fc = D[D.t == tl].copy(); fc['계절'] = season(cut, fc)
b = tr.dropna(subset=['lp', '계절']); mpf = lgbr(b, b.lp - b.계절, F); fc['pf'] = mpf.predict(fc[F]); fc['chg'] = 0.0; fc['chg_ns'] = 0.0
W_ = wsel[2025]; fc = forms(fc, W_); fc = fc.join(qs[2025].rename(columns={0.1: 'q10', 0.9: 'q90'}), on='h')
fc['예측_원kg'] = np.exp(fc.f_섞기); fc['하한10'] = np.exp(fc.f_섞기 + fc.q10); fc['상한90'] = np.exp(fc.f_섞기 + fc.q90)
fc['작년같은달_원kg'] = np.exp(fc.ly_lp); fc['평균판_원kg'] = np.exp(fc.f_가격없음LGB); fc['기준월_원kg'] = np.exp(fc.lp_t)
ym = lambda mi: f'{mi // 12}-{mi % 12 + 1:02d}'
fc['기준월'] = fc.t.map(ym); fc['목표월'] = fc.m.map(ym); fc['출하량_작년같은달_톤'] = np.expm1(fc.ly_q) / 1000
PI = pd.read_csv(OUTD / '_입력' / '01x_품종월_패널_최대확장.csv.gz', usecols=['계열키', '품목명', '계열', '계열구분']).drop_duplicates('계열키').set_index('계열키')
fc = fc.join(PI, on='계열키')
cols = ['계열키', '품목명', '계열', '계열구분', '기준월', '목표월', 'h', '예측_원kg', '하한10', '상한90', '작년같은달_원kg', '평균판_원kg', '기준월_원kg', '월보adj', '출하량_작년같은달_톤']
fc[cols].round(3).to_csv(OUT2 / '06_최신_1년예측_새기준.csv', index=False, encoding='utf-8-sig')
print('최신 예측', ym(tl), len(fc), '줄 | 계열', fc.계열키.nunique(), '| w', W_, flush=True)
# ======== 요인(M04): 가격 없는 LGB(평균판 편차) 변수 묶음별 기여 — 최신 예측 줄, SHAP
G = {'계절·달력': ['h', '목표달', '목표sin', '목표cos'], '품목 구분': ['품목코드'], '품종 자기 물량': ['규모', 'ly_q', 'ly2_q', '목표달비중', '품종_12m변화', '품종_3m변화'],
     '품목 전체 물량': ['품목_12m변화', '품목_3m변화'], '면적·생산 공표': [c for c in PC], '월보 생산 전망': ['월보신호']}
pc = mpf.predict(fc[F], pred_contrib=True)[:, :-1]; pcd = pd.DataFrame(pc, columns=F, index=fc.index)
gs = pd.DataFrame({g: pcd[[c for c in cs if c in F]].sum(axis=1) for g, cs in G.items()})
gs['계열키'] = fc.계열키.values; gs['h'] = fc.h.values; gs['월보×b(출발가격 쪽)'] = fc.월보adj.values
gs.round(4).to_csv(OUT2 / '07_요인_기여_최신.csv', index=False, encoding='utf-8-sig')
ab = gs[list(G)].abs().mean(); print('요인 비중(%)', (ab / ab.sum() * 100).round(1).to_dict())
