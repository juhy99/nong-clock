"""1단계: DB → 원인 모델 입력 패널 (11-11)

  python python-ml/1_panel.py            # DB 에서 읽어 model/panel_<기준일>/ 에 저장 + 채워진 정도 보고
읽는 DB 표: variety_unit · price_unit_daily(322단위 일별 시세) · production_yearly(연 생산) · weather_warning_daily(특보) · price_origin_daily(산지 비중)
읽는 기준표: python-ml/ref/unit_supply_v3b.csv (단위 → 공급 단위·철·모델·재배묶음, 변수표_원인모델_1111.md)
만드는 것 (예측 코드 2·3단계가 이것만 읽음 — 그때 쓴 자료를 그대로 다시 볼 수 있게 스냅샷):
  unit_daily.csv.gz   단위 × 거래일: 물량·금액·단가
  item_daily.csv.gz   품목 전국(국산·ALL) × 거래일: 물량·금액 (품목 계절 곡선용)
  supply_yearly.csv   공급 단위 × 수확 해: 생산·면적·연 가격 + dq · dp · 되돌림 (원인 모델 34·35번과 같은 식)
  x4_yearly.csv       과수 공급 단위 × 해: 여름(6~8월) 태풍특보 비중 합, 주산지 시·도 생산 비중으로 가중 (38번 X4)
  unit_supply.csv     기준표 그대로
  coverage.csv        단위마다 변수가 얼마나 채워졌는지
가격은 기준점(작년 같은 철 수준·계절 모양)과 정답에만 쓴다 — 이 패널의 어떤 변수도 '지금 가격'이 아니다 (강사님 원칙).
"""

import sys

import numpy as np
import pandas as pd

import config as C

AREA_ONLY = {"옥수수"}  # 35번: 면적만 있는 공급 단위 → 단수 대신 생산(=면적) 그대로
X4_MONTHS = (6, 7, 8)    # 38번 과수 W2 창
X4_SHARE_YEARS = (2020, 2022)


def supply_yearly(py: pd.DataFrame) -> pd.DataFrame:
    """원인 모델 34번(all50/panel.py)·35번(s5/build35.py)과 같은 식"""
    out = []
    for su, x in py.sort_values(["supply_unit", "year"]).groupby("supply_unit"):
        x = x.set_index("year").copy()
        x["lP"] = np.log(x.price_year.astype(float))
        x["dp"] = x.lP.diff()
        lQ = np.log(x.production_t.astype(float))
        x["dq"] = lQ.diff()
        need = 8 if (x.source == "35번").all() else 10
        A = x.area_ha.astype(float)
        if A.notna().sum() > need and su not in AREA_ONLY:
            x["da"] = np.log(A).diff()
            lY = lQ - np.log(A)
        else:
            x["da"] = np.nan
            lY = lQ
        x["되돌림"] = lY.shift(1) - lY.shift(2).rolling(5, min_periods=3).mean()
        out.append(x.reset_index())
    return pd.concat(out, ignore_index=True)


def x4_yearly(con, us: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """과수 공급 단위 × 해: Σ 시·도 생산 비중 × Σ(6~8월 그날 태풍특보 구역 비중)"""
    fr = us[us.x4_typhoon == 1]
    if fr.empty:
        return pd.DataFrame(columns=["supply_unit", "year", "x4"])
    w = C.query(con, "SELECT date, region_id, area_share FROM weather_warning_daily WHERE warn_type = '태풍' AND EXTRACT(MONTH FROM date) IN (6, 7, 8)")
    if w.empty:
        return pd.DataFrame(columns=["supply_unit", "year", "x4"])
    w["year"] = pd.to_datetime(w.date).dt.year
    W = w.groupby(["year", "region_id"]).area_share.sum().astype(float).unstack(fill_value=0.0)
    # 특보 기록이 있는 여름(6~8월)인데 태풍특보가 없던 해 = 0 (기록 시작 2016-11 → 2017년 여름부터)
    span = C.query(con, "SELECT min(date) AS a, max(date) AS b FROM weather_warning_daily").iloc[0]
    a, b = pd.Timestamp(span.a), pd.Timestamp(span.b)
    years = [y for y in range(a.year, b.year + 1) if pd.Timestamp(y, 6, 1) >= a and pd.Timestamp(y, 8, 31) <= b]
    W = W.reindex(years, fill_value=0.0)
    items = units.set_index("unit_name").item_code.to_dict()
    rows = []
    for su, g in fr.groupby(fr.supply_unit.where(fr.supply_unit != "", fr.unit_name)):
        codes = sorted({items[u] for u in g.unit_name})
        months = sorted({((int(s) - 1 + i) % 12) + 1 for s, n in zip(g.season_start, g.season_months) for i in range(int(n))})
        sh = C.query(con, "SELECT origin_region_id AS region_id, sum(volume_kg) AS v FROM price_origin_daily "
                          "WHERE market_code = 'national' AND NOT is_import AND item_code = ANY(%s) AND EXTRACT(YEAR FROM date) BETWEEN %s AND %s "
                          "AND EXTRACT(MONTH FROM date) = ANY(%s) AND origin_region_id > 0 GROUP BY 1",
                     (codes, X4_SHARE_YEARS[0], X4_SHARE_YEARS[1], months))
        if sh.empty:
            continue
        s = (sh.set_index("region_id").v.astype(float) / sh.v.astype(float).sum()).reindex(W.columns, fill_value=0.0)
        for y, val in (W * s).sum(axis=1).items():
            rows.append(dict(supply_unit=su, year=int(y), x4=round(float(val), 4)))
    return pd.DataFrame(rows)


def main():
    con = C.connect()
    units = C.query(con, "SELECT unit_id, unit_name, item_code, months, main_region_id FROM variety_unit")
    us = pd.read_csv(C.REF / "unit_supply_v3b.csv", keep_default_na=False)
    missing = set(units.unit_name) ^ set(us.unit_name)
    if missing:
        sys.exit(f"variety_unit 과 기준표가 다름: {sorted(missing)[:10]}")
    daily = C.query(con, "SELECT unit_id, date, volume_kg, amount_won, price FROM price_unit_daily ORDER BY unit_id, date")
    # 품목 전국 시세(국산·ALL) — 단위 기록이 짧을 때 쓰는 "품목 계절 곡선" 재료
    item_daily = C.query(con, "SELECT item_code, date, volume_kg, amount_won FROM price_daily WHERE market_code = 'national' AND grade = 'ALL' ORDER BY item_code, date")
    base = pd.to_datetime(daily.date).max().date()
    py = C.query(con, "SELECT supply_unit, year, production_t, area_ha, price_year, source FROM production_yearly")
    sy = supply_yearly(py)
    x4 = x4_yearly(con, us, units)
    out = C.model_dir() / f"panel_{base:%Y%m%d}"
    out.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out / "unit_daily.csv.gz", index=False, encoding="utf-8", compression="gzip")
    item_daily.to_csv(out / "item_daily.csv.gz", index=False, encoding="utf-8", compression="gzip")
    sy.to_csv(out / "supply_yearly.csv", index=False, encoding="utf-8")
    x4.to_csv(out / "x4_yearly.csv", index=False, encoding="utf-8")
    us.to_csv(out / "unit_supply.csv", index=False, encoding="utf-8")
    units.to_csv(out / "units.csv", index=False, encoding="utf-8")
    for f in ("unit_shape_v3b.csv", "supply_unit_v3b.csv"):
        pd.read_csv(C.REF / f, keep_default_na=False).to_csv(out / f, index=False, encoding="utf-8")

    # ── 채워진 정도 (단위마다) ──
    d = daily.assign(date=pd.to_datetime(daily.date))
    g = d.groupby("unit_id")
    cov = pd.DataFrame({"시세_첫날": g.date.min().dt.date, "시세_끝날": g.date.max().dt.date,
                        "거래일_2023이후": d[d.date >= "2023-01-01"].groupby("unit_id").size()})
    sy_ok = sy.dropna(subset=["dq", "dp"]).groupby("supply_unit").size()
    rv = sy.dropna(subset=["되돌림"])
    rows = []
    for un, gg in us.groupby("unit_name", sort=False):
        uid = int(gg.unit_id.iloc[0])
        sus = [s for s in gg.supply_unit if s]
        c = cov.loc[uid] if uid in cov.index else None
        rows.append(dict(unit_id=uid, 예측단위=un, 모델=gg.model.iloc[0], 공급단위=" · ".join(sus) or "(없음: MA)",
                         시세_첫날=c["시세_첫날"] if c is not None else None, 시세_끝날=c["시세_끝날"] if c is not None else None,
                         거래일_2023이후=int(c["거래일_2023이후"]) if c is not None and pd.notna(c["거래일_2023이후"]) else 0,
                         탄력_학습해수=int(max([sy_ok.get(s, 0) for s in sus], default=0)),
                         되돌림_2023_2026=",".join(str(y) for y in sorted(set(rv[rv.supply_unit.isin(sus) & rv.year.between(2023, 2026)].year))),
                         X4=int(gg.x4_typhoon.iloc[0]),
                         X4_해수=int(x4[x4.supply_unit.isin(sus or [un])].year.nunique()) if len(x4) else 0))
    R = pd.DataFrame(rows)
    R.to_csv(out / "coverage.csv", index=False, encoding="utf-8-sig")
    print(f"패널 → {out}  (시세 기준일 {base}, 단위 {len(R)}, 일별 {len(daily):,}줄, 공급 단위 {sy.supply_unit.nunique()}, X4 {len(x4)}줄)")
    print("모델:", R.모델.value_counts().to_dict())
    print("2023년 뒤 거래일 0인 단위:", int((R.거래일_2023이후 == 0).sum()))
    s0 = R[R.모델 == "S0"]
    print(f"S0 {len(s0)}단위 중 탄력을 자기 기록으로 배울 수 있는 단위(8해 이상): {int((s0.탄력_학습해수 >= 8).sum())}, "
          f"되돌림이 2023~2026 중 하나라도 있는 단위: {int((s0.되돌림_2023_2026 != '').sum())}")
    print(f"X4 대상 {int(R.X4.sum())}단위 중 특보 해가 있는 단위: {int(((R.X4 == 1) & (R.X4_해수 > 0)).sum())}")
    return R


if __name__ == "__main__":
    main()
