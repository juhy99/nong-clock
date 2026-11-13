import sys, numpy as np, pandas as pd
sys.path.insert(0, sys.argv[3]); import combine as K
T = pd.read_csv(sys.argv[1]); O = pd.read_csv(sys.argv[2])
T = T[T.출하철 == 1]
O["기준월"] = pd.to_datetime(O.출발).dt.to_period("M").astype(str)
M = T.merge(O, on=["예측단위", "기준월", "목표월"], how="inner")
M = M[(M.선택 > 0) & (M.실제 > 0) & (M.예측_원kg > 0)]
M = M.assign(단위=M.예측단위, yr=M.목표월.str[:4].astype(int), xt=np.log(M.예측_원kg), xo=np.log(M.선택), xa=np.log(M.실제),
             grp=np.where(M.h <= 3, "h1-3", np.where(M.h <= 6, "h4-6", "h7-12")))
print("팀원 출하철 줄", len(T), "→ 같은 줄", len(M), "| 실제 비(팀원/우리) 중앙", round((M.실제_원kg / M.실제).median(), 4))
R, best = K.run(M, "월 1~12달")
# 참고: 팀원 자기 실제로
R2, _ = K.run(M.assign(xa=np.log(M.실제_원kg)), "월 (참고: 팀원 실제로 채점)")
# 거리별
for n in ("A", "B"):
    c = "xt" if n == "A" else "xo"
    g = M[M.yr >= 2025].groupby("h").apply(lambda x: K.score(x, c)).round(1)
    print(n, "확인 h별", g.to_dict())
M.to_csv(sys.argv[4], index=False, compression="gzip")
