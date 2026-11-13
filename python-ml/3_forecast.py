"""3단계: 세 모델을 섞어 화면용 일 단위 예측 표 만들기 (11-12)

  python python-ml/3_forecast.py --engine <run 폴더>/forecast_unit_daily.csv.gz --v4 <01 월 예측 csv> --u7c <05 일 예측 322단위 csv>
                                 --panel <panel 폴더> --items shared/items50.json --out <표 폴더>
  → <표 폴더>/price_forecast_daily.csv  (load_db.py 가 DB price_forecast_daily 에 넣음)

섞는 규칙 (돌리기 전에 정함 — 비율은 설계_모델비교_합치기_1112.md 결과, 팀원 재학습 뒤 다시 정하면 W_DAY · W_MONTH 만 바꿈)
  ① 1~14거래일 (u7c 예측이 있는 날): log 값 = W_DAY × u7c + (1 − W_DAY) × 원인
  ② 그 뒤 v4 마지막 목표월까지: 원인 일 예측 × (v4 월 값 ÷ 원인 월 평균) ^ W_MONTH
       → 달 평균 수준 = exp(W_MONTH·log v4 + (1 − W_MONTH)·log 원인), 달 안 날짜별 모양 = 원인 모델
  ③ 그 뒤 ~ 기준일 + 365일: 원인 모델만
  한쪽만 있으면 있는 쪽 (②에서 원인이 없는 날 = v4 월 값 그대로). 둘 다 없으면 그날은 줄 없음 (화면 '예측 없음')
  v4 는 출하철 = 1 인 달만 (팀원 성적도 출하철만), u7c 는 구분 = 일별만
  최대 365일 (팀 결정)
  [사후 추가 11-12, 화면 이음 — 첫 결과에서 일요일 톱니·15일째 계단(최대 15%)을 보고 넣음. 정확도 규칙은 그대로]
  ⓐ ① 구간 안의 거래 없는 날(일요일·휴장)은 앞뒤 ① 값 사이 log 직선
  ⓑ ① 마지막 날 뒤 FADE 일 동안 ①과 ②의 차이를 직선으로 줄여 이음 (FADE = 14)
  ⓕ [사후 추가 11-13, 팀원 제안] v4 월 값은 그 달 금액÷물량이고, ②는 날짜 값의 평균을 v4 에 맞춤 → 기준이 달라
     v4 월 값 ÷ 보정비(ref/v4_보정표_1113.csv '쓸값' = 금액÷물량 ÷ 일 단가 단순평균, 단위 × 달, 2020~25 중앙)로 날짜 평균 기준으로 바꿔 씀.
     표에 없는 단위·달은 1. 보정비는 0.9~1.1 로 자름 (11-13: 철 시작 달처럼 몇 kg 거래가 일 평균을 끌어올린 달은 0.49 같은 값이 있어
     달 전체가 2배가 됨 → 극단 달만 덜 움직이게). 정확도 규칙(비율)은 그대로. 팀원 검증: 차이 중앙 2.01 → 1.86%
  [11-13 팀원 제안] 출하철 밖: 그날 묶인 단위들의 무게 절반 넘게가 v4 출하철(01 파일 출하철 = 1) 밖 달이면 off_season = 1
     (두 모델 다 그 달은 채점해 본 적이 없어 정확도를 모름 → 화면에 '참고' 표시)

품종·품목으로 묶기: 단위 값의 가중 평균. 무게 = 그 단위의 작년 같은 달 물량 (기준일 앞 가장 최근 같은 달, DB price_unit_daily).
  그날 예측이 있는 단위만으로 무게를 다시 나눔. 무게가 전부 0 이면 같은 무게. 품목(variety_id = ALL) = 품목의 모든 품종 단위
범위(하한·상한): 고르기 구간(목표 2023~24) 섞은 예측의 log(실제 ÷ 예측) 10%·90% 분위, 거리 묶음별 (ref/forecast_band.csv)
가격은 출발점·계절 모양·정답에만 — 이 표 어디에도 '지금 시세'를 입력으로 쓰지 않음 (강사님 원칙)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
W_DAY = 0.7     # 1~14거래일: u7c(u7d) 비중 — 11-12 저녁 재비교(팀원 새판)로 정함
W_MONTH = 1.0   # 15거래일~12달: v4 비중 (달 평균 수준) — 재비교에서 v4 단독이 뽑힘
MAX_DAYS = 365
ADJ_LO, ADJ_HI = 0.9, 1.1   # ⓕ 보정비를 자르는 범위


def band_of(days: int, seg: str, B: pd.DataFrame):
    """거리(일)·구간 → (q10, q90) log 비"""
    if seg == "일":
        r = B[B.구간 == "일"]
        r = r.iloc[(r.거리 - min(days, 14)).abs().argsort()[:1]]
    else:
        m = min(12, max(1, round(days / 30.4)))
        r = B[(B.구간 == ("월" if seg == "월" else "원인")) & (B.거리 == m)]
    return float(r.q10.iloc[0]), float(r.q90.iloc[0])


def unit_forecasts(a) -> pd.DataFrame:
    """단위 × 목표일 → log 값 · 어느 규칙 · 범위 구간"""
    E = pd.read_csv(a.engine, parse_dates=["base_date", "target_date"])
    base = pd.Timestamp(a.base) if a.base else None
    V = pd.read_csv(a.v4)
    season = {(u, int(m[5:7])) for u, m in zip(V[V.출하철 == 1].예측단위, V[V.출하철 == 1].목표월)}  # 단위 × 달(1~12) 출하철
    V = V[V.출하철 == 1][["예측단위", "목표월", "예측_원kg"]].rename(columns={"예측단위": "unit", "예측_원kg": "v4"})
    if a.adj and Path(a.adj).exists():   # ⓕ 보정비
        A = pd.read_csv(a.adj, encoding="utf-8-sig")[["예측단위", "달", "쓸값"]].rename(columns={"예측단위": "unit", "달": "m"})
        V = V.assign(m=V.목표월.str[5:7].astype(int)).merge(A, on=["unit", "m"], how="left")
        V["v4"] = V.v4 / V.쓸값.fillna(1.0).clip(ADJ_LO, ADJ_HI)
        print(f"ⓕ v4 보정비: {V.쓸값.notna().mean() * 100:.1f}% 줄에 적용 · 중앙 {V.쓸값.median():.4f}")
        V = V.drop(columns=["m", "쓸값"])
    D = pd.read_csv(a.u7c, parse_dates=["기준일", "목표일"])
    D = D[D.구분 == "일별"][["단위", "기준일", "목표일", "새기준_원kg"]].rename(columns={"단위": "unit", "목표일": "date", "새기준_원kg": "u7c"})
    base = base or D.기준일.max()
    end = base + pd.Timedelta(days=MAX_DAYS)
    E = E[(E.target_date > base) & (E.target_date <= end)][["unit_name", "target_date", "price"]].rename(columns={"unit_name": "unit", "target_date": "date", "price": "cause"})
    E["목표월"] = E.date.dt.strftime("%Y-%m")
    cm = E.groupby(["unit", "목표월"]).cause.apply(lambda s: np.exp(np.log(s).mean())).rename("cause_m").reset_index()
    v4_end = pd.Period(V.목표월.max(), "M").end_time.normalize()
    # 날짜 뼈대: 원인 예측 날 ∪ u7c 날 ∪ (v4 달의 모든 날 — 원인이 없는 단위·달)
    days = pd.date_range(base + pd.Timedelta(days=1), end)
    units = sorted(set(E.unit) | set(V.unit) | set(D.unit))
    G = pd.MultiIndex.from_product([units, days], names=["unit", "date"]).to_frame(index=False)
    G["목표월"] = G.date.dt.strftime("%Y-%m")
    G = G.merge(E[["unit", "date", "cause"]], on=["unit", "date"], how="left").merge(cm, on=["unit", "목표월"], how="left")
    G = G.merge(V, on=["unit", "목표월"], how="left").merge(D[["unit", "date", "u7c"]], on=["unit", "date"], how="left")
    u7_last = D.date.max()
    G = G.sort_values(["unit", "date"]).reset_index(drop=True)
    # ⓒ [사후 추가] 달이 바뀌는 날 계단을 없애려고, 달마다 값(v4 log · 높이 보정)을 그 달 15일에 두고 이웃 달 15일 사이를 직선으로
    #    (예전 월 예측기 db_predictor 와 같은 방식). 이웃 달 값이 없으면 그 달 값 그대로
    G["adj"] = W_MONTH * (np.log(G.v4) - np.log(G.cause_m))
    G["lv4"] = np.log(G.v4)
    for col in ("adj", "lv4"):
        mv = G.groupby(["unit", "목표월"])[col].first().dropna()
        mid = pd.to_datetime(mv.index.get_level_values(1) + "-15")
        pts = pd.DataFrame({"unit": mv.index.get_level_values(0), "mid": mid, "v": mv.values})
        sm = np.full(len(G), np.nan)
        for u, ix in G.groupby("unit").indices.items():
            p = pts[pts.unit == u].sort_values("mid")
            if p.empty:
                continue
            x = (G.date.iloc[ix] - base).dt.days.to_numpy(); xp = (p.mid - base).dt.days.to_numpy(); yp = p.v.to_numpy()
            y = np.interp(x, xp, yp)
            # 이웃 달이 비어 있는 곳(철 끝)은 직선 대신 그 달 값
            gap = np.diff(xp) > 45
            for j in np.flatnonzero(gap):
                inb = (x > xp[j]) & (x < xp[j + 1])
                y[inb] = np.where(x[inb] - xp[j] < xp[j + 1] - x[inb], yp[j], yp[j + 1])
            own = G[col].iloc[ix].to_numpy()
            y = np.where(np.isfinite(own), y, np.nan)   # 그 달 값이 있는 날만
            if col == "adj":   # ⓓ [사후 추가] v4 철 앞뒤 30일은 보정을 0 까지 직선으로 줄임 (철 끝 계단 방지)
                have = np.flatnonzero(np.isfinite(y))
                if len(have):
                    for j in np.flatnonzero(~np.isfinite(y)):
                        n = have[np.abs(have - j).argmin()]
                        dist = abs(x[j] - x[n])
                        if dist <= 30:
                            y[j] = y[n] * (1 - dist / 30)
            sm[ix] = y
        G[col + "_s"] = sm
    lc, lv, lu, lm = np.log(G.cause), G.lv4_s, np.log(G.u7c), np.log(G.cause) * 0
    # ②·③ 값 (모든 날에 대해 먼저 계산 — 이음에 씀)
    b = np.full(len(G), np.nan); rule = np.full(len(G), "", dtype=object); seg = np.full(len(G), "", dtype=object)
    s2 = (G.date <= v4_end) & G.v4.notna()
    b2 = s2 & G.cause.notna()
    b[b2] = lc[b2] + G.adj_s[b2]; rule[b2] = ("v4 높이 + 원인 모양" if W_MONTH == 1 else f"v4 {W_MONTH:g} 높이 + 원인 모양"); seg[b2] = "월"
    o2 = s2 & G.cause.isna()
    b[o2] = lv[o2]; rule[o2] = "v4 월 값"; seg[o2] = "월"
    s3 = ~s2 & G.cause.notna()
    f3 = s3 & G.adj_s.notna()
    b[s3] = lc[s3] + np.where(f3[s3], G.adj_s[s3], 0.0); rule[s3] = np.where(f3[s3], "원인 (v4 철 이음)", "원인"); seg[s3] = "원인"
    # ⓔ [사후 추가] ②·③ 은 단위마다 이어진 날끼리 가운데 7일 log 평균으로 다듬음 (원인 엔진의 작은 단위 톱니). ① 은 그대로
    bs = pd.Series(b).groupby([G.unit, (G.date.diff().dt.days.ne(1) | G.unit.ne(G.unit.shift())).cumsum()])
    b = np.where(np.isfinite(b), bs.transform(lambda s: s.rolling(7, center=True, min_periods=1).mean()).to_numpy(), np.nan)  # 예측 없던 날은 그대로 비움
    # ① 값
    one = np.where(G.cause.notna(), W_DAY * lu + (1 - W_DAY) * lc, lu)
    one[G.u7c.isna().to_numpy()] = np.nan
    out = b.copy()
    FADE = 14
    for u, ix in G.groupby("unit").indices.items():
        o1 = one[ix]
        k = np.flatnonzero(np.isfinite(o1))
        if not len(k):
            continue
        a0, a1 = k[0], k[-1]
        span = np.arange(a0, a1 + 1)
        out[ix[span]] = np.interp(span, k, o1[k])               # ⓐ 사이 날 직선
        r1 = np.where(np.isfinite(o1[span]), (f"u7c {W_DAY:g} + 원인 {1 - W_DAY:g}" if G.cause.notna().iloc[ix[a1]] else "u7c"), "u7c 사이 날")
        rule[ix[span]] = r1; seg[ix[span]] = "일"
        if np.isfinite(b[ix[a1]]):                              # ⓑ 이음
            delta = out[ix[a1]] - b[ix[a1]]
            for j in range(a1 + 1, min(len(ix), a1 + 1 + FADE)):
                if np.isfinite(b[ix[j]]):
                    out[ix[j]] = b[ix[j]] + delta * (1 - (j - a1) / FADE)
                    rule[ix[j]] = rule[ix[j]] + " (이음)"
    G["lp"], G["rule"], G["seg"] = out, rule, seg
    G = G[np.isfinite(G.lp)].copy()
    G["days"] = (G.date - base).dt.days
    G["in_season"] = [(u, m) in season for u, m in zip(G.unit, G.date.dt.month)]
    print(f"기준일 {base.date()} · 끝 {end.date()} · u7c 끝 {u7_last.date()} · v4 끝 {v4_end.date()} · 단위 {G.unit.nunique()} · 줄 {len(G):,}")
    print("규칙별 줄:", G.rule.value_counts().to_dict())
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
    out = []
    for item, vid, us in groups:
        g = G[G.unit.isin(us)]
        if g.empty:
            continue
        g = g.assign(w=g.groupby("date").w.transform(lambda s: s / s.sum() if s.sum() > 0 else 1.0 / len(s)))
        p = (g.w * np.exp(g.lp)).groupby(g.date).sum()
        # 그날 가장 무게가 큰 단위의 규칙·구간을 대표로
        top = g.sort_values("w").groupby("date").tail(1).set_index("date")
        on = (g.w * g.in_season).groupby(g.date).sum()   # 출하철인 단위의 무게 몫
        r = pd.DataFrame({"price": p, "rule": top.rule, "seg": top.seg, "days": top.days, "off_season": (on < 0.5).astype(int)})
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
    print(f"출하철 밖 줄 (off_season): {int(R.off_season.sum()):,} / {len(R):,}")
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    R.to_csv(o / "price_forecast_daily.csv", index=False, encoding="utf-8")
    print(f"→ {o / 'price_forecast_daily.csv'}: {len(R):,}줄 · 품목 {R.item_code.nunique()} · 품종 {(R.variety_id != 'ALL').groupby(R.item_code).size().size} 품목에 {R[R.variety_id != 'ALL'].variety_id.nunique()}개")


if __name__ == "__main__":
    main()
