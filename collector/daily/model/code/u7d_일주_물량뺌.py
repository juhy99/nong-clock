# u7d (11-12): u7c에서 물량 항(28일 국산 출하량 전년비 × β)을 뺌 — 팀 원칙(반입량 안 씀). 새기준 = w × 작년 같은 주 + (1 − w) × 주 계절평균. 입력 일별 파일을 인자로 받음(최신 원장까지). 사용: python u7c_일주_최신.py <출력폴더> <70_일주_단위일별가격 csv.gz>
import sys, numpy as np, pandas as pd, time
OUT = sys.argv[1]; SRC = sys.argv[2]; t0 = time.time()
A = pd.read_csv(SRC, parse_dates=['date'])
rows = [A.copy()]
info = A.groupby('단위').agg(품목=('품목', 'first'), 묶음=('묶음', 'first'))
A = A.dropna(subset=['p']); A['lp'] = np.log(A.p)
iso = A.date.dt.isocalendar(); A['wk'] = iso.week.clip(upper=52).astype(int); A['yr'] = iso.year.astype(int)
# 공급: 단위 국산 물량 28일 합 전년비(그날까지)
SUP = {}
for nm, g in pd.concat(rows).groupby('단위'):
    s = g.set_index('date').국산_kg.asfreq('D').fillna(0).rolling(28, min_periods=14).sum()
    SUP[nm] = np.log((s + 1) / (s.shift(364) + 1))
W = A.groupby(['단위', 'yr', 'wk']).agg(lp=('lp', 'mean'), date=('date', 'max'), q=('국산_kg', 'sum')).reset_index()
def build(kind):
    out = []
    if kind == '주별':
        for v, g in W.groupby('단위'):
            g = g.sort_values(['yr', 'wk']).reset_index(drop=True); idx = {(a, b): i for i, (a, b) in enumerate(zip(g.yr, g.wk))}
            for H in (1, 2, 3, 4):
                for i in range(len(g)):
                    y, w = g.yr[i], g.wk[i]; w2, y2 = w + H, y
                    while w2 > 52: w2 -= 52; y2 += 1
                    j = idx.get((y2, w2))
                    if j is None: continue
                    a = idx.get((y2 - 1, w2))
                    out.append((v, H, g.date[i], g.date[j], y2, w2, g.lp[j], g.lp[a] if a is not None else np.nan, g.lp[i], g.q[j]))
    else:
        for v, g in A.groupby('단위'):
            g = g.sort_values('date').reset_index(drop=True); wk = W[W.단위 == v].set_index(['yr', 'wk']).lp
            for H in range(1, 15):
                if len(g) <= H: continue
                i = np.arange(len(g) - H); j = i + H
                anc = wk.reindex(list(zip(g.yr.values[j] - 1, g.wk.values[j]))).values
                out.extend(zip([v] * len(i), [H] * len(i), g.date.values[i], g.date.values[j], g.yr.values[j], g.wk.values[j], g.lp.values[j], anc, g.lp.values[i], g.국산_kg.values[j]))
    Z = pd.DataFrame(out, columns=['단위', 'H', '기준일', '목표일', 'yr', 'wk', 'lp', 'anc', 'lp_now', 'q'])
    Z['기준일'] = pd.to_datetime(Z.기준일); Z['목표일'] = pd.to_datetime(Z.목표일); Z['sup'] = np.nan
    for v, g in Z.groupby('단위'): Z.loc[g.index, 'sup'] = SUP[v].reindex(pd.DatetimeIndex(g.기준일)).values
    return Z
for kind in ('주별', '일별'):
    Z = build(kind); Z['ty'] = Z.목표일.dt.year; print(kind, '줄', len(Z), round(time.time() - t0), '초', flush=True)
    def fit(cut, rows):
        tr = Z[Z.ty < cut]; sm = tr.groupby(['단위', 'wk']).lp.mean(); sk = tr.groupby('단위').lp.mean()
        z = rows.copy(); z['계절'] = [sm.get((a, b), np.nan) for a, b in zip(z.단위, z.wk)]; z['계절'] = z.계절.fillna(z.단위.map(sk))
        c = tr.dropna(subset=['anc', 'sup']); y = (c.lp - c.anc).clip(-1.5, 1.5); xx = c.sup.clip(-2, 2)
        beta = 0.0   # u7d: 물량 항 안 씀
        z['작년x공급'] = z.anc + beta * z.sup.fillna(0).clip(-2, 2); return z, beta
    outs = []; wsel = {}
    for Y in (2023, 2024, 2025):
        va, _ = fit(Y - 1, Z[Z.ty == Y - 1]); best = None
        for w in np.round(np.arange(0, 1.01, 0.1), 1):
            f = np.where(va.anc.notna(), w * va.작년x공급 + (1 - w) * va.계절, va.계절)
            e = pd.Series(np.abs(np.exp(f - va.lp) - 1) * 100).groupby(va.단위.values).mean().median()
            if best is None or e < best[1]: best = (w, e)
        te, beta = fit(Y, Z[Z.ty >= Y] if Y == 2025 else Z[Z.ty == Y]); w = best[0]; wsel[Y] = (w, round(beta, 3))
        te['섞기'] = np.where(te.anc.notna(), w * te.작년x공급 + (1 - w) * te.계절, te.계절)
        te['반반'] = np.where(te.anc.notna(), 0.5 * te.anc + 0.5 * te.계절, te.계절)
        te['3개평균'] = (te.섞기 + te.반반 + te.계절) / 3
        te['시험'] = str(Y) if Y < 2025 else '2025~'; outs.append(te)
    R = pd.concat(outs).dropna(subset=['계절']); R.to_pickle(OUT + f'/_u7_{kind}.pkl')
    M = {'새기준': '섞기', '3개평균': '3개평균', '계절평균': '계절', '작년같은주': 'anc', '참고_지난값그대로(가격흐름·금지)': 'lp_now'}
    for k_, c in M.items(): R['e_' + k_] = (np.exp(R[c] - R.lp) - 1).abs() * 100
    T = R.groupby('H').apply(lambda g: pd.Series({k_: round(100 - g.groupby('단위')['e_' + k_].mean().median(), 1) for k_ in M} | {'단위수': g.단위.nunique(),
        '방향적중%': round((np.sign(g.섞기 - g.lp_now) == np.sign(g.lp - g.lp_now)).mean() * 100, 1)}))
    print(kind, 'w·β', wsel); print(T.to_string()); T.to_csv(OUT + f'/{71 if kind == "주별" else 72}_{kind}_성적.csv', encoding='utf-8-sig')
    S = R.groupby(['단위', 'H']).e_새기준.mean().unstack(); S.columns = [f'{kind}_H{c}' for c in S.columns]
    S = (100 - S).round(1); S.to_csv(OUT + f'/_u7_{kind}_단위.csv', encoding='utf-8-sig')
    # 최신 예측: 마지막 기준일에서 앞으로
    last = A.date.max(); tr_all = Z; sm = tr_all.groupby(['단위', 'wk']).lp.mean(); sk = tr_all.groupby('단위').lp.mean()
    c = tr_all.dropna(subset=['anc', 'sup']); y = (c.lp - c.anc).clip(-1.5, 1.5); xx = c.sup.clip(-2, 2); beta = 0.0   # u7d: 물량 항 안 씀
    w = wsel[2025][0]; fc = []
    for v in A.단위.unique():
        sv = SUP[v].get(last, np.nan) if last in SUP[v].index else np.nan
        bd = pd.bdate_range(last + pd.Timedelta(days=1), periods=20, freq='C', weekmask='Mon Tue Wed Thu Fri Sat')
        HS = (1, 2, 3, 4) if kind == '주별' else tuple(range(1, 15))
        for H in HS:
            tg = last + pd.Timedelta(days=7 * H) if kind == '주별' else bd[H - 1]; iso_ = tg.isocalendar(); wk_ = min(iso_.week, 52); yr_ = iso_.year
            se = sm.get((v, wk_), sk.get(v, np.nan)); an = W[(W.단위 == v) & (W.yr == yr_ - 1) & (W.wk == wk_)].lp
            an = an.iloc[0] if len(an) else np.nan
            f = w * (an + beta * (0 if np.isnan(sv) else np.clip(sv, -2, 2))) + (1 - w) * se if not np.isnan(an) else se
            ban = 0.5 * an + 0.5 * se if not np.isnan(an) else se
            fc.append((v, kind, H, last.date(), tg.date(), np.exp(f), np.exp((f + ban + se) / 3), np.exp(an) if not np.isnan(an) else np.nan))
    F = pd.DataFrame(fc, columns=['단위', '구분', 'H', '기준일', '목표일', '새기준_원kg', '3개평균_원kg', '작년같은주_원kg']).round(0)
    F.to_csv(OUT + f'/{74 if kind == "주별" else 75}_최신_{kind}예측.csv', index=False, encoding='utf-8-sig')
S = pd.read_csv(OUT + '/_u7_주별_단위.csv', index_col=0).join(pd.read_csv(OUT + '/_u7_일별_단위.csv', index_col=0), how='outer').join(info, how='right')
S.to_csv(OUT + '/73_단위별_일주성적.csv', encoding='utf-8-sig'); print('끝', round(time.time() - t0), '초')
