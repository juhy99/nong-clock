"""3단계: 세 모델을 섞어 화면용 일 단위 예측 표 만들기 (11-12, 11-16 팀 최종 정리 PDF 규칙으로 바꿈)

  python python-ml/3_forecast.py --engine <run 폴더>/forecast_unit_daily.csv.gz --v4 <01 월 예측 csv> --u7c <05 일 예측 322단위 csv>
                                 --panel <panel 폴더> --items shared/items50.json --out <표 폴더>
  → <표 폴더>/price_forecast_daily.csv  (load_db.py 가 DB price_forecast_daily 에 넣음)

규칙 (팀 최종 모델 76판 정리 PDF 'UNIT 05 365일 일별' 그대로, 11-16)
  ① 1~14거래일 (u7d 예측이 있는 날): log 값 = W_DAY × u7d + (1 − W_DAY) × 원인        ← 팀 합의 11-13
  ② 그 뒤 v4 마지막 목표월까지: 그 달 v4 월 예측 × 날짜 모양
       날짜 모양 = 그 단위의 과거 요일 패턴 + 그 달 안 몇째 주 패턴 (2021~기준일, 해마다 같은 무게)
         몇째 주 효과는 주 가운데 날(4·11·18·25·29.5일)에 두고 사이 날은 직선으로 이음 (11-16: 7일 칸 경계 계단 없앰,
         2024·2025 시험에서 칸 방식보다 정확도 +0.3·+0.2, 하루 계단 상위 10% 7.5% → 6.3%)
       달 안 거래일(월~토) 값의 평균 = v4 월 값 (ⓕ 보정비로 '날 평균' 기준으로 바꾼 값)
  ①→② 사이: ① 마지막 날 뒤 FADE(14일 ≈ 10거래일) 동안 차이를 직선으로 줄여 이음 (PDF '다음 10거래일')
  ③ v4 끝 다음 달 ~ 기준일 + 365일: 평년 × 마지막 예측 달 비율 × 날짜 모양 → 참고 값 (off_season = 1 로 표시)
       평년 = 그 단위·그 달 최근 5년 달 평균의 기하평균, 비율 = 마지막 v4 달 값 ÷ 그 달 평년
  출하철 밖(그 단위 연 물량 95%를 덮는 달이 아닌 달)은 단위 값 없음 (PDF: 빈칸) · 일요일 없음 (휴장)
  원인 모델은 ① 의 0.3 에만 씀

품종·품목으로 묶기: 단위 값의 가중 평균. 무게 = 그 단위의 작년 같은 달 물량 (기준일 앞 가장 최근 같은 달).
  그날 값이 있는 단위의 무게가 묶음 전체 무게의 절반 미만이면 그날은 줄 없음 (11-16: 감귤 2027-11 처럼 비싼 몇 품종만 남아 값이 튀는 것 막음)
범위(하한·상한): 고르기 구간(목표 2023~24)의 log(실제 ÷ 예측) 10%·90% 분위, 거리 묶음별 (ref/forecast_band.csv)
가격은 출발점·계절 모양·정답에만 — 이 표 어디에도 '지금 시세'를 입력으로 쓰지 않음 (강사님 원칙)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
W_DAY = 0.7     # 1~14거래일: u7d 비중 (팀 합의 11-13)
MAX_DAYS = 365
ADJ_LO, ADJ_HI = 0.9, 1.1   # ⓕ 보정비를 자르는 범위
FADE = 14       # ①→② 이음 (달력 14일 ≈ 10거래일)
SHAPE_YEARS = 5
PK_CENTER = np.array([4.0, 11.0, 18.0, 25.0, 29.5])   # 몇째 주(0~4) 효과를 두는 날
COVER_MIN = 0.5  # 묶음에서 값 있는 단위 무게 몫이 이보다 작으면 그날 줄 없음


def band_of(days: int, seg: str, B: pd.DataFrame):
    """거리(일)·구간 → (q10, q90) log 비"""
    if seg == "일":
        r = B[B.구간 == "일"]
        r = r.iloc[(r.거리 - min(days, 14)).abs().argsort()[:1]]
    else:
        m = min(12, max(1, round(days / 30.4)))
        r = B[(B.구간 == "월") & (B.거리 == m)]
    return float(r.q10.iloc[0]), float(r.q90.iloc[0])


def history(panel: Path, base: pd.Timestamp) -> pd.DataFrame:
    ud = pd.read_csv(panel / "unit_daily.csv.gz", parse_dates=["date"])
    un = pd.read_csv(panel / "units.csv").set_index("unit_id").unit_name
    ud["unit"] = ud.unit_id.map(un)
    ud = ud[(ud.date <= base) & (ud.price > 0)]
    return ud[ud.date > base - pd.DateOffset(years=SHAPE_YEARS)][["unit", "date", "price"]]


def shape_tables(H: pd.DataFrame):
    """과거 일 시세 → 요일 효과 (단위 × 요일) · 몇째 주 효과 (단위 × 달 × 주) · 평년 (단위 × 달)"""
    H = H.copy()
    H["lp"] = np.log(H.price)
    H["ym"] = H.date.dt.to_period("M")
    g = H.groupby(["unit", "ym"])
    H["n"] = g.lp.transform("size")
    H = H[H.n >= 8]
    H["r"] = H.lp - H.groupby(["unit", "ym"]).lp.transform("mean")
    H["dow"] = H.date.dt.dayofweek
    H["m"], H["y"], H["k"] = H.date.dt.month, H.date.dt.year, ((H.date.dt.day - 1) // 7).clip(upper=4)
    wd = H.groupby(["unit", "dow"]).r.agg(["mean", "size"])
    wd = (wd["mean"] * wd["size"] / (wd["size"] + 20)).rename("wd").reset_index()
    H = H.merge(wd, on=["unit", "dow"], how="left")
    H["r2"] = H.r - H.wd
    py = H.groupby(["unit", "m", "k", "y"]).r2.mean().reset_index()       # 해마다 같은 무게
    pk = py.groupby(["unit", "m", "k"]).r2.agg(["mean", "size"])
    pk = (pk["mean"] * pk["size"] / (pk["size"] + 1)).rename("pk").reset_index()
    mon = H.groupby(["unit", "ym"]).price.mean().reset_index()            # 달 평균 (날 단순평균)
    mon["m"] = mon.ym.dt.month
    nor = mon.groupby(["unit", "m"]).price.apply(lambda s: float(np.exp(np.log(s).mean()))).rename("normal").reset_index()
    return wd, pk, nor


def week_effect(G: pd.DataFrame, pk: pd.DataFrame) -> np.ndarray:
    """단위 × 달 × 날 → 몇째 주 효과를 주 가운데 날 사이 직선으로 이은 값 (없는 주는 0)"""
    piv = pk.pivot_table(index=["unit", "m"], columns="k", values="pk").reindex(columns=range(5)).fillna(0.0)
    V = G[["unit", "m"]].merge(piv.reset_index(), on=["unit", "m"], how="left")[list(range(5))].fillna(0.0).to_numpy()
    d = G.date.dt.day.to_numpy().astype(float)
    j = np.clip(np.searchsorted(PK_CENTER, d, side="right") - 1, 0, 3)
    t = np.clip((d - PK_CENTER[j]) / (PK_CENTER[j + 1] - PK_CENTER[j]), 0.0, 1.0)   # 4일 앞·29.5일 뒤는 끝 값 그대로
    r = np.arange(len(d))
    return V[r, j] * (1 - t) + V[r, j + 1] * t


def unit_forecasts(a) -> pd.DataFrame:
    """단위 × 목표일 → log 값 · 규칙 · 범위 구간 · 참고 여부"""
    E = pd.read_csv(a.engine, parse_dates=["base_date", "target_date"])
    V = pd.read_csv(a.v4)
    season = {(u, int(m[5:7])) for u, m in zip(V[V.출하철 == 1].예측단위, V[V.출하철 == 1].목표월)}  # 단위 × 달(1~12) 출하철
    V = V[V.출하철 == 1][["예측단위", "목표월", "예측_원kg"]].rename(columns={"예측단위": "unit", "예측_원kg": "v4"}).dropna()
    if a.adj and Path(a.adj).exists():   # ⓕ 보정비 (v4 = 금액÷물량 → 날 단순평균 기준)
        A = pd.read_csv(a.adj, encoding="utf-8-sig")[["예측단위", "달", "쓸값"]].rename(columns={"예측단위": "unit", "달": "m"})
        V = V.assign(m=V.목표월.str[5:7].astype(int)).merge(A, on=["unit", "m"], how="left")
        V["v4"] = V.v4 / V.쓸값.fillna(1.0).clip(ADJ_LO, ADJ_HI)
        print(f"ⓕ v4 보정비: {V.쓸값.notna().mean() * 100:.1f}% 줄에 적용 · 중앙 {V.쓸값.median():.4f}")
        V = V.drop(columns=["m", "쓸값"])
    D = pd.read_csv(a.u7c, parse_dates=["기준일", "목표일"])
    D = D[D.구분 == "일별"][["단위", "기준일", "목표일", "새기준_원kg"]].rename(columns={"단위": "unit", "목표일": "date", "새기준_원kg": "u7"})
    base = pd.Timestamp(a.base) if a.base else D.기준일.max()
    end = base + pd.Timedelta(days=MAX_DAYS)
    E = E[(E.target_date > base) & (E.target_date <= end)][["unit_name", "target_date", "price"]].rename(columns={"unit_name": "unit", "target_date": "date", "price": "cause"})
    v4_end = pd.Period(V.목표월.max(), "M").end_time.normalize()

    wd, pk, nor = shape_tables(history(Path(a.panel), base))
    units = sorted(set(V.unit) | set(D.unit))
    # 날짜 뼈대: 기준일 다음 날 ~ 365일, 일요일 뺌. 정규화를 위해 첫 달·마지막 달은 달 전체를 깔고 나중에 자름
    days = pd.date_range(base.replace(day=1), end + pd.offsets.MonthEnd(0))
    days = days[days.dayofweek != 6]
    G = pd.MultiIndex.from_product([units, days], names=["unit", "date"]).to_frame(index=False)
    G["m"], G["dow"], G["k"] = G.date.dt.month, G.date.dt.dayofweek, ((G.date.dt.day - 1) // 7).clip(upper=4)
    G["목표월"] = G.date.dt.strftime("%Y-%m")
    G["in_season"] = [(u, m) in season for u, m in zip(G.unit, G.m)]
    G = G.merge(wd, on=["unit", "dow"], how="left").reset_index(drop=True)
    G["pk"] = week_effect(G, pk)
    G["s"] = (G.wd.fillna(0) + G.pk).clip(-0.4, 0.4)
    G["es"] = np.exp(G.s)
    G["es"] = G.es / G.groupby(["unit", "목표월"]).es.transform("mean")   # 달 안 거래일 평균 = 1
    G = G.merge(V, on=["unit", "목표월"], how="left").merge(nor, on=["unit", "m"], how="left")
    # ③ 비율 = 그 단위 마지막 v4 달 값 ÷ 그 달 평년
    last = V.assign(m=V.목표월.str[5:7].astype(int)).merge(nor, on=["unit", "m"]).sort_values("목표월").groupby("unit").tail(1)
    ratio = (last.v4 / last.normal).rename("ratio")
    ratio.index = last.unit
    G["ratio"] = G.unit.map(ratio)
    G = G[(G.date > base) & (G.date <= end)].merge(E, on=["unit", "date"], how="left").merge(D[["unit", "date", "u7"]], on=["unit", "date"], how="left")
    G = G.sort_values(["unit", "date"]).reset_index(drop=True)

    b = np.full(len(G), np.nan); rule = np.full(len(G), "", dtype=object); seg = np.full(len(G), "", dtype=object); ref = np.zeros(len(G), bool)
    s2 = (G.date <= v4_end) & G.v4.notna()
    b[s2] = np.log(G.v4[s2] * G.es[s2]); rule[s2] = "v4 × 날짜 모양"; seg[s2] = "월"
    s3 = (G.date > v4_end) & G.normal.notna() & G.ratio.notna()
    b[s3] = np.log(G.normal[s3] * G.ratio[s3] * G.es[s3]); rule[s3] = "평년 × 비율 (참고)"; seg[s3] = "월"; ref[s3] = True
    one = np.where(G.cause.notna(), W_DAY * np.log(G.u7) + (1 - W_DAY) * np.log(G.cause), np.log(G.u7))
    out = b.copy()
    for u, ix in G.groupby("unit").indices.items():
        o1 = one[ix]
        k = np.flatnonzero(np.isfinite(o1))
        if not len(k):
            continue
        a1 = k[-1]
        out[ix[k]] = o1[k]
        rule[ix[k]] = np.where(G.cause.iloc[ix[k]].notna(), f"u7d {W_DAY:g} + 원인 {1 - W_DAY:g}", "u7d"); seg[ix[k]] = "일"; ref[ix[k]] = False
        if np.isfinite(b[ix[a1]]):
            delta = out[ix[a1]] - b[ix[a1]]
        else:   # ① 마지막 날에 ② 값이 없으면 (철 끝 등) 다음 ② 첫 값 기준
            nxt = [j for j in range(a1 + 1, len(ix)) if np.isfinite(b[ix[j]])]
            delta = (out[ix[a1]] - b[ix[nxt[0]]]) if nxt else 0.0
        d0 = G.date.iloc[ix[a1]]
        for j in range(a1 + 1, len(ix)):
            dd = (G.date.iloc[ix[j]] - d0).days
            if dd >= FADE:
                break
            if np.isfinite(b[ix[j]]):
                out[ix[j]] = b[ix[j]] + delta * (1 - dd / FADE)
                rule[ix[j]] = rule[ix[j]] + " (이음)"
    G["lp"], G["rule"], G["seg"], G["ref"] = out, rule, seg, ref
    G = G[np.isfinite(G.lp) & G.in_season].copy()      # 출하철 밖 = 빈칸
    G["days"] = (G.date - base).dt.days
    print(f"기준일 {base.date()} · 끝 {end.date()} · u7d 끝 {D.date.max().date()} · v4 끝 {v4_end.date()} · 단위 {G.unit.nunique()} · 줄 {len(G):,}")
    print("규칙별 줄:", G.rule.str.replace(" (이음)", "", regex=False).value_counts().to_dict())
    return G, base


def weights(panel: Path, base: pd.Timestamp) -> pd.DataFrame:
    """단위 × 달(1~12) → 기준일 앞 가장 최근 같은 달 물량"""
    ud = pd.read_csv(panel / "unit_daily.csv.gz", parse_dates=["date"])
    un = pd.read_csv(panel / "units.csv").set_index("unit_id").unit_name
    ud["unit"] = ud.unit_id.map(un)
    ud = ud[ud.date <= base]
    ud["y"], ud["m"] = ud.date.dt.year, ud.date.dt.month
    rows = []
    for m in range(1, 13):
        y = base.year if (m < base.month) else base.year - 1  # 기준일 달은 아직 덜 찼으니 작년
        g = ud[(ud.y == y) & (ud.m == m)].groupby("unit").volume_kg.sum()
        rows.append(pd.DataFrame({"unit": g.index, "m": m, "w": g.values}))
    return pd.concat(rows)


def main():
    ap = argparse.ArgumentParser()
    for k in ("engine", "v4", "u7c", "panel", "items", "out"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--band", default=str(HERE / "ref" / "forecast_band.csv"))
    ap.add_argument("--adj", default=str(HERE / "ref" / "v4_보정표_1113.csv"), help="ⓕ v4 보정비 표 (빈 값이면 안 씀)")
    ap.add_argument("--base", default="", help="기준일 (기본: u7c 기준일)")
    a = ap.parse_args()
    G, base = unit_forecasts(a)
    B = pd.read_csv(a.band)
    W = weights(Path(a.panel), base)
    G["m"] = G.date.dt.month
    G = G.merge(W, on=["unit", "m"], how="left")
    G["w"] = G.w.fillna(0.0)
    items = json.load(open(a.items, encoding="utf-8"))["items"]
    groups = []
    for it in items:
        allu = []
        for v in it.get("varieties", []):
            groups.append((it["code"], v["id"], v["units"])); allu += v["units"]
        groups.append((it["code"], "ALL", allu))
    WM = W.copy()
    out = []
    for item, vid, us in groups:
        g = G[G.unit.isin(us)]
        if g.empty:
            continue
        tot = WM[WM.unit.isin(us)].groupby("m").w.sum()                # 묶음 전체 무게 (달별)
        cov = g.groupby("date").w.sum() / g.groupby("date").m.first().map(tot)
        g = g.assign(w=g.groupby("date").w.transform(lambda s: s / s.sum() if s.sum() > 0 else 1.0 / len(s)))
        p = (g.w * np.exp(g.lp)).groupby(g.date).sum()
        top = g.sort_values("w").groupby("date").tail(1).set_index("date")
        refw = (g.w * g.ref).groupby(g.date).sum()
        r = pd.DataFrame({"price": p, "rule": top.rule, "seg": top.seg, "days": top.days, "off_season": (refw >= 0.5).astype(int), "cov": cov})
        r = r[r["cov"].fillna(0) >= COVER_MIN].drop(columns="cov")
        if r.empty:
            continue
        q = np.array([band_of(int(d), s, B) for d, s in zip(r.days, r.seg)])
        r["price_low"], r["price_high"] = r.price * np.exp(q[:, 0]), r.price * np.exp(q[:, 1])
        r = r.reset_index().rename(columns={"date": "target_date"})
        r["item_code"], r["variety_id"] = item, vid
        out.append(r)
    R = pd.concat(out, ignore_index=True)
    R["base_date"] = base.date()
    R["target_date"] = R.target_date.dt.date
    for c in ("price", "price_low", "price_high"):
        R[c] = R[c].round().astype(int)
    R = R.rename(columns={"rule": "model"})[["base_date", "item_code", "variety_id", "target_date", "price", "price_low", "price_high", "model", "off_season"]]
    print(f"참고(평년×비율) 줄 (off_season=1): {int(R.off_season.sum()):,} / {len(R):,}")
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    R.to_csv(o / "price_forecast_daily.csv", index=False, encoding="utf-8")
    print(f"→ {o / 'price_forecast_daily.csv'}: {len(R):,}줄 · 품목 {R.item_code.nunique()} · 품종 {(R.variety_id != 'ALL').groupby(R.item_code).size().size} 품목에 {R[R.variety_id != 'ALL'].variety_id.nunique()}개")


if __name__ == "__main__":
    main()
