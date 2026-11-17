"""3단계: 세 모델을 섞어 화면용 일 단위 예측 표 만들기 (11-12, 11-16 팀 최종 정리 PDF 규칙으로 바꿈)

  python python-ml/3_forecast.py --engine <run 폴더>/forecast_unit_daily.csv.gz --v4 <01 월 예측 csv> --u7c <05 일 예측 322단위 csv>
                                 --panel <panel 폴더> --items shared/items50.json --out <표 폴더>
  → <표 폴더>/price_forecast_daily.csv  (load_db.py 가 DB price_forecast_daily 에 넣음)

규칙 (팀 최종 모델 76판 정리 PDF 'UNIT 05 365일 일별' 그대로, 11-16)
  ① 1~14거래일 (u7d 예측이 있는 날): log 값 = W_DAY × u7d + (1 − W_DAY) × 원인        ← 팀 합의 11-13
  ② 그 뒤 v4 마지막 목표월까지: 그 달 v4 월 예측 × 날짜 모양
       날짜 모양 = 그 단위의 과거 요일 패턴 (2021~기준일). [11-17] '몇째 주 패턴'(11-16)은 뺌 — 아래 이어진 달 수준이 대신함
       달 안 거래일(월~토) 값의 평균 = v4 월 값 (ⓕ 보정비로 '날 평균' 기준으로 바꾼 값)
       [11-17] 달 수준은 계단이 아니라 이어진 선: 달 가운데(15.5일)에 점을 두고 사이를 직선으로 이은 뒤,
         달마다 평균이 v4 값과 같아지도록 점 높이를 몇 번 고침 (SMOOTH_ITER). 출하철이 끊기는 곳은 잇지 않음.
         → 달이 바뀌는 날 값이 뛰던 것 없앰 (11-17 점검: 품목 전체 20% 넘는 달 경계 61번)
  ①→② 사이: ① 마지막 날 뒤 FADE(14일 ≈ 10거래일) 동안 차이를 직선으로 줄여 이음 (PDF '다음 10거래일')
  ③ v4 끝 다음 달 ~ 기준일 + 365일: 평년 × 마지막 예측 달 비율 × 날짜 모양 → 참고 값 (off_season = 1 로 표시)
       평년 = 그 단위·그 달 최근 5년 달 평균의 기하평균, 비율 = 마지막 v4 달 값 ÷ 그 달 평년
  출하철 밖(그 단위 연 물량 95%를 덮는 달이 아닌 달)은 단위 값 없음 (PDF: 빈칸) · 일요일 없음 (휴장)
  원인 모델은 ① 의 0.3 에만 씀
  ⓖ [11-14 폭락 보정, 사용자 결정 — PDF 에는 없음, 결정_폭락상태_보정시험_1114] 상태 = 기준일까지 7일 단위 금액합÷물량합 ÷ 364일 전 같은 7일.
     상태가 0.67 이하인 단위만 ① 값(log)에 ref/crash_adjust_1114.csv 의 곱을 더함 (≤0.5: 1~5거래일 ×0.71 · 6~14 ×0.79 / 0.5~0.67: ×0.84 · ×0.90).
     ① 값을 고친 뒤 이음(delta)을 계산하므로 이음 14일도 같이 줄어듦. 두 주 중 하나라도 거래가 없으면 상태를 모름 → 보정 안 함.
     지금 시세는 '폭락인지' 판단에만 씀 (강사님 원칙의 예외로 문서에 적음). 품목·품종 줄의 crash_adj = 보정 단위가 하나라도 섞임

품종·품목으로 묶기: 단위 값의 가중 평균. 무게 = 그 단위의 작년 같은 달 물량 (기준일 앞 가장 최근 같은 달).
  그날 값이 있는 단위의 무게가 묶음 전체 무게의 절반 미만이면 그날은 줄 없음 (11-16: 감귤 2027-11 처럼 비싼 몇 품종만 남아 값이 튀는 것 막음)
범위(하한·상한): 고르기 구간(목표 2023~24)의 log(실제 ÷ 예측) 10%·90% 분위, 거리 묶음별 (ref/forecast_band.csv)
가격은 출발점·계절 모양·정답에만 — '지금 시세'는 ⓖ 폭락 판단(예외, 1~14거래일)에만 씀 (강사님 원칙)
(11-14 ⓗ '얇은 달 참고' 규칙은 위 '무게 절반 미만이면 줄 없음'이 대신함 — 예: 자두 12월은 작년 물량 0 → 줄 없음)
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
COVER_MIN = 0.5
SMOOTH_ITER = 6  # [11-17] 달 수준 이은 선: 달 평균 맞추기 반복 횟수  # 묶음에서 값 있는 단위 무게 몫이 이보다 작으면 그날 줄 없음


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


def crash_state(panel: Path, base: pd.Timestamp) -> pd.Series:
    """ⓖ 단위 → 상태 (기준일까지 7일 금액÷물량 ÷ 364일 전 같은 7일). 두 주 중 하나라도 거래 없으면 빠짐"""
    ud = pd.read_csv(panel / "unit_daily.csv.gz", parse_dates=["date"])
    un = pd.read_csv(panel / "units.csv").set_index("unit_id").unit_name
    ud = ud[ud.volume_kg > 0].assign(unit=lambda d: d.unit_id.map(un))
    def wk(end):
        g = ud[(ud.date > end - pd.Timedelta(days=7)) & (ud.date <= end)].groupby("unit")
        return g.amount_won.sum() / g.volume_kg.sum()
    return (wk(base) / wk(base - pd.Timedelta(days=364))).dropna()


def crash_factor(state: float, h: int, T: pd.DataFrame) -> float:
    """ⓖ 상태·거래일 거리 → log 곱 (해당 없으면 0)"""
    r = T[(T.상태_이상 < state) & (state <= T.상태_미만) & (T.H_부터 <= h) & (h <= T.H_까지)]
    return float(np.log(r.곱.iloc[0])) if len(r) else 0.0


def smooth_level(dates: np.ndarray, ym: np.ndarray, es: np.ndarray, tgt: np.ndarray) -> np.ndarray:
    """[11-17] 한 단위의 날짜별 달 목표값(tgt, 없으면 nan) → 달 평균(es 곱한 날 평균)은 목표와 같고 달 사이가 이어진 수준.
    목표가 있는 달이 이어진 구간마다 따로 (출하철이 끊기면 따로). 구간 첫 달 앞·끝 달 뒤는 평평"""
    lev = np.full(len(dates), np.nan)
    months = pd.unique(ym[np.isfinite(tgt)])
    if not len(months):
        return lev
    per = pd.PeriodIndex(months, freq="M")
    order = np.argsort(per.asi8)
    per, months = per[order], months[order]
    segs, cur = [], [0]
    for i in range(1, len(per)):
        if (per[i] - per[i - 1]).n == 1:
            cur.append(i)
        else:
            segs.append(cur); cur = [i]
    segs.append(cur)
    t_day = dates.astype("datetime64[D]").astype(np.int64).astype(float)
    for sg in segs:
        ms = months[sg]
        mid = np.array([(p.start_time + pd.Timedelta(days=(p.end_time - p.start_time).days / 2)).value // 86_400_000_000_000 for p in per[sg]], float)
        idx = [np.flatnonzero(ym == m) for m in ms]
        goal = np.array([np.log(np.nanmean(tgt[ix])) for ix in idx])
        anc = goal.copy()
        rows = np.concatenate(idx)
        for _ in range(SMOOTH_ITER):
            L = np.interp(t_day[rows], mid, anc)                    # 끝 밖은 평평
            lev[rows] = L
            for k, ix in enumerate(idx):
                anc[k] += goal[k] - np.log(np.mean(np.exp(lev[ix]) * es[ix]))
        lev[rows] = np.interp(t_day[rows], mid, anc)
    return np.exp(lev)


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
    # [11-17] 달 수준을 이어진 선으로 바꾸면서 '몇째 주 효과'는 뺌 — 이어진 선이 달 안 오르내림을 이미 그려서, 같이 쓰면 두 번 세어 달 끝이 튐
    #   (2024·2025 시험, 달 평균을 안다고 칠 때: 계단+요일+주 84.75·84.15 → 이음+요일 84.82·84.17, 달 경계 하루 변화 중앙 16.6% → 2.5%)
    G["s"] = G.wd.fillna(0).clip(-0.4, 0.4)
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
    s2 = ((G.date <= v4_end) & G.v4.notna()).to_numpy()
    s3 = ((G.date > v4_end) & G.normal.notna() & G.ratio.notna()).to_numpy()
    # [11-17] 달 목표값(출하철 달만) → 이어진 수준. 달 평균은 그대로라 v4 정확도는 같음
    tgt = np.where(s2, G.v4, np.where(s3, G.normal * G.ratio, np.nan)).astype(float)
    tgt[~G.in_season.to_numpy()] = np.nan
    lev = np.full(len(G), np.nan)
    ymv, dv, esv = G["목표월"].to_numpy(), G.date.to_numpy(), G.es.to_numpy()
    for u, ix in G.groupby("unit").indices.items():
        lev[ix] = smooth_level(dv[ix], ymv[ix], esv[ix], tgt[ix])
    ok = np.isfinite(lev)
    b[ok & s2] = np.log(lev[ok & s2] * esv[ok & s2]); rule[s2] = "v4 × 날짜 모양"; seg[s2] = "월"
    b[ok & s3] = np.log(lev[ok & s3] * esv[ok & s3]); rule[s3] = "평년 × 비율 (참고)"; seg[s3] = "월"; ref[s3] = True
    one = np.where(G.cause.notna(), W_DAY * np.log(G.u7) + (1 - W_DAY) * np.log(G.cause), np.log(G.u7))
    # ⓖ 폭락 보정: 단위마다 ① 날을 거래일 순서(H=1..)로 세어 곱을 더함 (이음 계산 전에)
    crash = np.zeros(len(G), dtype=bool)
    if getattr(a, "crash", "") and Path(a.crash).exists():
        T = pd.read_csv(a.crash)
        st = crash_state(Path(a.panel), base)
        hit = {}
        for u, ix in G.groupby("unit").indices.items():
            sv = st.get(u)
            if sv is None or sv > T.상태_미만.max():
                continue
            for h, j in enumerate(ix[np.isfinite(one[ix])], start=1):
                f = crash_factor(float(sv), h, T)
                if f:
                    one[j] += f; crash[j] = True
            hit[u] = round(float(sv), 2)
        print(f"ⓖ 폭락 보정: 상태 잰 단위 {len(st)} · 보정 {len(hit)}단위 (≤0.5 {sum(v <= .5 for v in hit.values())})")
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
                crash[ix[j]] = crash[ix[j]] or bool(crash[ix[k]].any())   # ⓖ 이음 날도 보정 표시
    G["lp"], G["rule"], G["seg"], G["ref"], G["crash"] = out, rule, seg, ref, crash
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
    ap.add_argument("--crash", default=str(HERE / "ref" / "crash_adjust_1114.csv"), help="ⓖ 폭락 보정 표 (빈 값이면 안 씀)")
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
        crw = (g.w * g.crash).groupby(g.date).sum()      # ⓖ 보정 단위의 무게 몫
        r = pd.DataFrame({"price": p, "rule": top.rule, "seg": top.seg, "days": top.days, "off_season": (refw >= 0.5).astype(int),
                          "crash_adj": (crw > 0).astype(int), "cov": cov})
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
    R = R.rename(columns={"rule": "model"})[["base_date", "item_code", "variety_id", "target_date", "price", "price_low", "price_high", "model", "off_season", "crash_adj"]]
    print(f"참고(평년×비율) 줄 (off_season=1): {int(R.off_season.sum()):,} / {len(R):,} · 폭락 보정 섞인 줄 (crash_adj): {int(R.crash_adj.sum()):,}")
    o = Path(a.out); o.mkdir(parents=True, exist_ok=True)
    R.to_csv(o / "price_forecast_daily.csv", index=False, encoding="utf-8")
    print(f"→ {o / 'price_forecast_daily.csv'}: {len(R):,}줄 · 품목 {R.item_code.nunique()} · 품종 {(R.variety_id != 'ALL').groupby(R.item_code).size().size} 품목에 {R[R.variety_id != 'ALL'].variety_id.nunique()}개")


if __name__ == "__main__":
    main()
