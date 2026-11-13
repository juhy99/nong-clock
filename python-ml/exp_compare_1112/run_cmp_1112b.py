"""11-12 저녁 재비교: 팀원 새판(반입량 뺌·새 정의·만감 합침) × 원인 모델(같은 새 정의 가격, 패널 2026-11-10). 규칙은 설계_모델비교_합치기_1112.md 그대로 + 사후 수정(월 정답 = DB 월 금액÷물량)"""
import sys, numpy as np, pandas as pd
S, T = sys.argv[1], sys.argv[2]; sys.path.insert(0, S + "/cmp"); import combine as K
P = S + "/model2/panel_20261110/"
ud = pd.read_csv(P + "unit_daily.csv.gz", parse_dates=["date"]); un = pd.read_csv(P + "units.csv").set_index("unit_id").unit_name
ud["단위"] = ud.unit_id.map(un); ud = ud[ud.volume_kg > 0]
# ── 월 ──
Tm = pd.read_csv(T + "/결과_기준202610/02_322_월예측_시험줄_2023부터.csv.gz"); Tm = Tm[Tm.출하철 == 1]
O = pd.read_csv(S + "/model2/run_20261110/test_monthly.csv"); O["기준월"] = pd.to_datetime(O.출발).dt.to_period("M").astype(str)
ud["목표월"] = ud.date.dt.strftime("%Y-%m")
g = ud.groupby(["단위", "목표월"]).agg(a=("amount_won", "sum"), v=("volume_kg", "sum"), n=("date", "size")).reset_index(); g = g[g.n >= 5]; g["월DB"] = g.a / g.v
M = Tm.merge(O, on=["예측단위", "기준월", "목표월"]).rename(columns={"예측단위": "단위"}).merge(g[["단위", "목표월", "월DB"]], on=["단위", "목표월"])
M = M[(M.선택 > 0) & (M.예측_원kg > 0)]
M = M.assign(yr=M.목표월.str[:4].astype(int), xt=np.log(M.예측_원kg), xo=np.log(M.선택), xa=np.log(M.월DB), grp=np.where(M.h <= 3, "h1-3", np.where(M.h <= 6, "h4-6", "h7-12")))
print("월: 팀원 출하철 줄", len(Tm), "→ 같은 줄", len(M), "| 팀원 실제 ÷ DB월 중앙", round(float((M.실제_원kg / M.월DB).median()), 4), "5%넘게", round(float(((M.실제_원kg / M.월DB - 1).abs() > .05).mean() * 100), 1), "%")
RM, bm = K.run(M, "월 1~12달 (정답 DB 월 금액÷물량)")
c26 = M[M.목표월.between("2026-01", "2026-10")]
for c, n in (("xt", "팀원"), ("xo", "원인")): print("  2026.01~10", n, round(K.score(c26, c), 2))
# ── 일 ──
R = pd.read_pickle(S + "/cmp2/u7/_u7_일별.pkl"); R = R[R.기준일.dt.weekday == 5][["단위", "H", "기준일", "목표일", "섞기"]]
R["출발"] = R.기준일 + pd.Timedelta(days=1)
Od = pd.read_csv(S + "/cmp2/our_daily.csv.gz", parse_dates=["출발", "목표일"])
D = R.merge(Od, on=["단위", "출발", "목표일"])
ud["xa"] = np.log(ud.amount_won / ud.volume_kg)
D = D.merge(ud[["단위", "date", "xa"]].rename(columns={"date": "목표일"}), on=["단위", "목표일"])
D = D.assign(yr=D.목표일.dt.year, xt=D.섞기, xo=D.lp_원인, grp=np.where(D.H <= 5, "H1-5", "H6-14"))
RD, bd = K.run(D, "일 1~14거래일 (정답 DB 그날 금액÷물량)")
M.to_csv(S + "/cmp2/month_rows.csv.gz", index=False, compression="gzip"); D.to_csv(S + "/cmp2/day_rows.csv.gz", index=False, compression="gzip")
