import sys, numpy as np, pandas as pd
S = sys.argv[1]; B = sys.argv[2].rstrip("/") + "/"   # 팀원 최종자료 폴더
def ue(df, col):
    return (np.exp(df[col] - df.xa) - 1).abs().groupby(df.단위).mean() * 100
out = {}
for kind, f, w in (("월", "month_rows", 0.6), ("일", "day_rows", 0.6)):
    M = pd.read_csv(f"{S}/cmp/{f}.csv.gz"); M["xc"] = w * M.xt + (1 - w) * M.xo
    for pn, sub in (("고르기", M[M.yr <= 2024]), ("확인", M[M.yr >= 2025])):
        for c, n in (("xt", "팀원"), ("xo", "원인"), ("xc", "섞기")):
            out[f"{kind}_{pn}_{n}"] = ue(sub, c)
        out[f"{kind}_{pn}_줄"] = sub.groupby("단위").size()
T = pd.DataFrame(out)
U = pd.read_csv(B + "데이터/05_322단위표_모델계열_부모_모델_출하철.csv")
us = pd.read_csv(S + "/model/panel_20261103/unit_supply.csv", keep_default_na=False)
ref = us.groupby("unit_name").agg(원인모델=("model", "first"), 공급단위=("supply_unit", lambda s: " · ".join(x for x in s if x) or "(없음)"),
    원인_철=("season_start", lambda s: ",".join(str(x) for x in s)), 원인_철달수=("season_months", lambda s: ",".join(str(x) for x in s)),
    X4=("x4_typhoon", "first"), 재배묶음=("cultivation_group", "first"))
cov = pd.read_csv(S + "/model/panel_20261103/coverage.csv").set_index("예측단위")[["탄력_학습해수", "되돌림_2023_2026", "X4_해수"]]
R = U.set_index("예측단위")[["품목명", "묶음", "들어간_품종", "모델", "모델계열키", "부모_품목합침_계열키", "출하철", "정확도_2023_24", "정확도_2025"]].rename(
    columns={"모델": "팀원모델", "출하철": "팀원_출하철"}).join(ref).join(cov).join(T)
R["원인모델"] = np.where((R.원인모델 == "S0") & (R.X4 == 1), "S0+X4", R.원인모델)
def better(r, k):
    v = {n: r.get(f"{k}_확인_{n}") for n in ("팀원", "원인", "섞기")}; v = {a: b for a, b in v.items() if pd.notna(b)}
    return min(v, key=v.get) if v else "비교 줄 없음"
R["월_확인에서_가장나은"] = R.apply(lambda r: better(r, "월"), axis=1); R["일_확인에서_가장나은"] = R.apply(lambda r: better(r, "일"), axis=1)
R.index.name = "예측단위"; R = R.round(1)
R.to_csv(S + "/cmp/단위별_비교_322.csv", encoding="utf-8-sig")
print(len(R)); print(R.월_확인에서_가장나은.value_counts().to_dict(), R.일_확인에서_가장나은.value_counts().to_dict())
print(R.groupby("품목명")[["월_확인_팀원", "월_확인_원인", "월_확인_섞기", "일_확인_팀원", "일_확인_원인", "일_확인_섞기"]].mean().round(1).to_string())
# 덮는 범위
Tm = pd.read_csv(B + "결과_기준202610/02_322_월예측_시험줄_2023부터.csv.gz"); Tm = Tm[Tm.출하철 == 1]
O = pd.read_csv(S + "/model/run_20261103/test_monthly.csv"); O["기준월"] = pd.to_datetime(O.출발).dt.to_period("M").astype(str); O = O[O.선택 > 0]
k = ["예측단위", "기준월", "목표월"]; a = Tm[k].drop_duplicates(); b = O[k].drop_duplicates()
mm = a.merge(b, how="outer", indicator=True); print(mm._merge.value_counts().to_dict())
print("팀원만 있는 줄의 목표달 분포(원인 철 밖):", mm[mm._merge == "left_only"].목표월.str[5:].value_counts().sort_index().to_dict())
