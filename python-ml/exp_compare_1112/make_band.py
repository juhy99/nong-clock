"""ref/forecast_band.csv 만들기: 고르기 구간(목표 2023~24) 섞은 예측의 log(실제 ÷ 예측) 10%·90% 분위, 거리별
  python make_band.py <비교 폴더(month_rows·day_rows)> <W_DAY> <W_MONTH> <출력 csv>"""
import sys, numpy as np, pandas as pd
d, wd, wm, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
M = pd.read_csv(d + "/month_rows.csv.gz"); M = M[M.yr <= 2024]
D = pd.read_csv(d + "/day_rows.csv.gz"); D = D[D.yr <= 2024]
rows = []
for h, s in (D.xa - (wd * D.xt + (1 - wd) * D.xo)).groupby(D.H): rows.append(("일", h, s.quantile(.1), s.quantile(.9), len(s)))
for name, pred in (("월", wm * M.xt + (1 - wm) * M.xo), ("원인", M.xo)):
    for h, s in (M.xa - pred).groupby(M.h): rows.append((name, h, s.quantile(.1), s.quantile(.9), len(s)))
B = pd.DataFrame(rows, columns=["구간", "거리", "q10", "q90", "줄"]).round(4); B.to_csv(out, index=False, encoding="utf-8")
print(B.assign(하한=(np.exp(B.q10) - 1) * 100, 상한=(np.exp(B.q90) - 1) * 100).round(0).iloc[[0, 13, 14, 25, 26, 37]].to_string(index=False))
