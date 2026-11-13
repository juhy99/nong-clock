# -*- coding: utf-8 -*-
"""단위 가격 표만 처음부터 다시 만들기 (11-12) — 단위 정의(ref/variety_unit_code.csv)를 바꾼 뒤에 씀
  python tools/rebuild_unit_prices.py 2020-01 2026-11      → <FARMBID_OUT>/price_unit_daily.csv (전 기간, 덮어씀)
build_tables.py 의 price_unit_daily 와 같은 계산: 달마다 원장을 읽어 같은 입력 오류 거르기(drop_entry_errors) → 산지를 아는 국산 줄만
→ (품목코드·품종코드·달)로 단위에 붙여 그날 전국 금액 합 ÷ 물량 합. price_daily · price_origin_daily 는 건드리지 않음
DB 에 넣을 때는 옛 줄이 남지 않게 표를 비우고 넣는다: NC_REPLACE=price_unit_daily python load_db.py
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_tables as B  # noqa: E402

m1, m2 = sys.argv[1], sys.argv[2]
m = dt.date.fromisoformat(m1 + '-01'); end = dt.date.fromisoformat(m2 + '-01')
it = B.ref('item')
uc = B.ref('variety_unit_code')
uc['months'] = uc.months.map(lambda s: [int(x) for x in s.split(',')] if s else list(range(1, 13)))
uc = uc.explode('months').rename(columns={'months': 'month'}); uc['month'] = uc.month.astype(int)
rid = dict(zip(B.ref('region').name, B.ref('region').region_id))
first, tot = True, 0
while m <= end:
    nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1)
    a = B.read_auction(m, nxt)
    a = a[a.date < nxt.isoformat()]
    a = a[a.code4.isin(it.code4)].copy()
    if not a.empty:
        a['up'] = a.총금액 / a.총물량
        a = B.drop_entry_errors(a)
        oo = a.산지명.map(B.origin_region)
        a['origin_region_id'] = [rid.get(s) if s else ('0' if imp else None) for s, imp in oo]
        a['is_import'] = [imp for _, imp in oo]
        dom = a[a.origin_region_id.notna() & ~a.is_import].copy()
        dom['month'] = pd.to_datetime(dom.date).dt.month
        j = dom.merge(uc, on=['code4', 'variety_code', 'month'], how='inner')
        g = j.groupby(['date', 'unit_id'], as_index=False).agg(volume_kg=('총물량', 'sum'), amount_won=('총금액', 'sum'))
        g['price'] = (g.amount_won / g.volume_kg).round().astype('Int64')
        g['volume_kg'] = g.volume_kg.round(1); g['amount_won'] = g.amount_won.round()
        B.save(g[['date', 'unit_id', 'volume_kg', 'amount_won', 'price']], 'price_unit_daily', first)
        first = False; tot += len(g)
    print(f'{m:%Y-%m} 끝 (누적 {tot:,}줄)', flush=True)
    m = nxt
