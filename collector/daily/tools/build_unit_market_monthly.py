# -*- coding: utf-8 -*-
"""시장 × 품종 단위 × 달 물량·금액 (11-12) — 시세 화면 '도매시장별 가격' 카드에서 품종을 골랐을 때 쓰는 표
  python tools/build_unit_market_monthly.py 2020-01 2026-11     → <FARMBID_OUT>/price_unit_market_monthly.csv
계산은 price_unit_daily 와 같음 (같은 입력 오류 거르기 · 산지를 아는 국산 줄 · ref/variety_unit_code.csv) — 다만 시장별로, 달 단위로 묶음.
품목 전체는 이 표가 필요 없음 (price_daily 의 시장 × 품목 ALL 등급 물량·금액으로)
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_tables as B  # noqa: E402

m = dt.date.fromisoformat(sys.argv[1] + '-01'); end = dt.date.fromisoformat(sys.argv[2] + '-01')
it = B.ref('item'); uc = B.ref('variety_unit_code')
uc['months'] = uc.months.map(lambda s: [int(x) for x in s.split(',')] if s else list(range(1, 13)))
uc = uc.explode('months').rename(columns={'months': 'month'}); uc['month'] = uc.month.astype(int)
rid = dict(zip(B.ref('region').name, B.ref('region').region_id))
first, tot = True, 0
while m <= end:
    nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1)
    a = B.read_auction(m, nxt)
    a = a[(a.date < nxt.isoformat()) & a.code4.isin(it.code4)].copy()
    if not a.empty:
        a['up'] = a.총금액 / a.총물량
        a = B.drop_entry_errors(a)
        oo = a.산지명.map(B.origin_region)
        a['origin_region_id'] = [rid.get(s) if s else ('0' if imp else None) for s, imp in oo]
        a['is_import'] = [imp for _, imp in oo]
        dom = a[a.origin_region_id.notna() & ~a.is_import].copy()
        dom['month'] = m.month
        j = dom.merge(uc, on=['code4', 'variety_code', 'month'], how='inner')
        j['market_code'] = j.도매시장코드.str.strip()
        g = j.groupby(['market_code', 'unit_id'], as_index=False).agg(volume_kg=('총물량', 'sum'), amount_won=('총금액', 'sum'), days=('date', 'nunique'))
        g.insert(0, 'month', m.isoformat())
        g['price'] = (g.amount_won / g.volume_kg).round().astype('Int64')
        g['volume_kg'] = g.volume_kg.round(1); g['amount_won'] = g.amount_won.round()
        B.save(g[['month', 'market_code', 'unit_id', 'volume_kg', 'amount_won', 'price', 'days']], 'price_unit_market_monthly', first)
        first = False; tot += len(g)
    print(f'{m:%Y-%m} 끝 (누적 {tot:,}줄)', flush=True)
    m = nxt
