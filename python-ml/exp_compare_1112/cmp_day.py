import sys, numpy as np, pandas as pd
S = sys.argv[1]; sys.path.insert(0, S + "/cmp"); import combine as K
R = pd.read_pickle(S + "/cmp/u7/_u7_일별.pkl")
R = R[R.기준일.dt.weekday == 5][["단위", "H", "기준일", "목표일", "lp", "섞기", "anc", "시험"]]
PAIR = ["천혜향", "레드향", "황금향", "카라향"]
R = R[~R.단위.isin([f"감귤 {v}" for v in PAIR] + [f"만감 {v}" for v in PAIR])]
O = pd.read_csv(S + "/cmp/our_daily.csv.gz", parse_dates=["출발", "목표일"])
R["출발"] = R.기준일 + pd.Timedelta(days=1)
M = R.merge(O, on=["단위", "출발", "목표일"], how="inner")
P = S + "/model/panel_20261103/"
ud = pd.read_csv(P + "unit_daily.csv.gz", parse_dates=["date"]); un = pd.read_csv(P + "units.csv").set_index("unit_id").unit_name
ud["단위"] = ud.unit_id.map(un); ud = ud[ud.volume_kg > 0]; ud["xa"] = np.log(ud.amount_won / ud.volume_kg)
M = M.merge(ud[["단위", "date", "xa"]].rename(columns={"date": "목표일"}), on=["단위", "목표일"], how="inner")
M = M.assign(yr=M.목표일.dt.year, xt=M.섞기, xo=M.lp_원인, grp=np.where(M.H <= 5, "H1-5", "H6-14"))
print("팀원 토요일 기준 줄", len(R), "원인 줄", len(O), "→ 같은 줄", len(M), "| 실제 비(팀원/DB) 중앙", round(float(np.exp(M.lp - M.xa).median()), 4))
Rr, best = K.run(M, "일 1~14거래일")
K.run(M.assign(xa=M.lp), "일 (참고: 팀원 실제로 채점)")
for c, n in (("xt", "A 팀원"), ("xo", "B 원인")):
    print(n, "확인 H별", M[M.yr >= 2025].groupby("H").apply(lambda x: K.score(x, c)).round(1).to_dict())
M["xly"] = M.anc
print("작년같은주 확인", round(K.score(M[(M.yr >= 2025) & M.anc.notna()], "xly"), 2), "(같은 줄 팀원", round(K.score(M[(M.yr >= 2025) & M.anc.notna()], "xt"), 2), "원인", round(K.score(M[(M.yr >= 2025) & M.anc.notna()], "xo"), 2), ")")
M.drop(columns=["lp"]).to_csv(S + "/cmp/day_rows.csv.gz", index=False, compression="gzip")
