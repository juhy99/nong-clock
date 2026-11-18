"""작물 추천용 주산지 표 만들기 (11-18) → shared/crop_regions.json

  python python-ml/crops/build_crop_regions.py --tables <자료 폴더>/05_DB적재/data/tables [--out shared/crop_regions.json]

무엇: 작물마다 '공영 도매시장에 들어온 국산 물량 가운데 그 시·도산이 몇 %인가' (최근 3년).
자료: DB 표 price_origin_daily 와 같은 CSV (build_tables.py 가 경매 정산 자료의 산지명을 시·도로 바꿔 만든 것) + region.csv
  - 수입(is_import)·산지 모름(origin_region_id = 0)·전국 합계 줄(market_code = national)은 뺌
  - 기간: 자료 마지막 날이 든 달의 앞 달까지 36달 (끝 달이 덜 찬 것을 피함)
      + month_share (11-18 저녁): 그 작물 국산 반입량의 달별 몫(1~12월 %, 같은 기간 36달 = 달마다 3번씩) — '수량 참고' 안내의 근거
쓰는 곳: ml-api/app/core/crop_regions.py — 그 시·도 몫이 main_pct 이상이면 '주산지'(위로), rare_pct 미만이면 '거의 안 기름'(아래로 + 안내)
주의: 재배면적이 아니라 '도매시장 반입 산지'다. 쌀·콩처럼 경매 자료에 없는 작물은 표에 없음 → 순위를 건드리지 않음.
손으로 고치지 말 것 — 이 코드를 다시 돌리기.
"""
import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

MAIN_PCT = 10.0   # 이 이상이면 주산지
RARE_PCT = 1.0    # 이 미만이면 거의 안 기름
MONTHS = 36


def build(tables: Path, crops_json: Path) -> dict:
    d = pd.read_csv(tables / "price_origin_daily.csv", usecols=["date", "market_code", "item_code", "origin_region_id", "is_import", "volume_kg"],
                    dtype={"market_code": str})
    last = pd.Timestamp(d.date.max())
    end = last.replace(day=1) - pd.Timedelta(days=1)                      # 앞 달 마지막 날
    start = (end + pd.Timedelta(days=1)) - pd.DateOffset(months=MONTHS)   # 36달 앞 1일
    d = d[(~d.is_import) & (d.origin_region_id > 0) & (d.market_code != "national")
          & (d.date >= start.strftime("%Y-%m-%d")) & (d.date <= end.strftime("%Y-%m-%d"))]
    names = pd.read_csv(tables / "region.csv").set_index("region_id").name
    g = d.groupby(["item_code", "origin_region_id"]).volume_kg.sum().unstack(fill_value=0.0)
    pct = g.div(g.sum(axis=1), axis=0) * 100
    codes = [c["code"] for c in json.loads(crops_json.read_text(encoding="utf-8"))["crops"]]
    # 11-18 저녁: 달별 몫 — 그 작물 국산 반입량이 1년 가운데 어느 달에 몇 % 들어오나 (1~12월, 합 100)
    gm = d.assign(m=d.date.str[5:7].astype(int)).groupby(["item_code", "m"]).volume_kg.sum().unstack(fill_value=0.0).reindex(columns=range(1, 13), fill_value=0.0)
    pm = gm.div(gm.sum(axis=1), axis=0) * 100
    share, month_share = {}, {}
    for code in codes:
        if code not in pct.index or g.loc[code].sum() <= 0:
            continue
        share[code] = {names[r]: round(float(pct.loc[code, r]), 1) for r in pct.columns}
        month_share[code] = [round(float(pm.loc[code, m]), 1) for m in range(1, 13)]
    return {
        "_about": "작물 추천용 주산지 표. python-ml/crops/build_crop_regions.py 가 만듦 (손으로 고치지 말 것). "
                  "값 = 공영 도매시장에 들어온 국산 물량 가운데 그 시·도산 몫(%) — 재배면적이 아니라 도매시장 반입 산지 기준. "
                  "자료: price_origin_daily (경매 정산 자료의 산지명). 여기 없는 작물(쌀·콩)은 순위를 건드리지 않음",
        "built_at": date.today().isoformat(),
        "period": [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")],
        "main_pct": MAIN_PCT,
        "rare_pct": RARE_PCT,
        "share": share,
        "month_share": month_share,
    }


if __name__ == "__main__":
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=repo / "shared" / "crop_regions.json")
    a = ap.parse_args()
    out = build(a.tables, repo / "shared" / "crops.json")
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{a.out}: 작물 {len(out['share'])}개 · 기간 {out['period'][0]}~{out['period'][1]}")
