# -*- coding: utf-8 -*-
"""단위 가격 표만 처음부터 다시 만들기 (11-12, 11-14 날 단위 오류 규칙 추가) — 단위 정의(ref/variety_unit_code.csv)·오류 규칙을 바꾼 뒤에 씀
  python tools/rebuild_unit_prices.py 2020-01 2026-11            → 한 번에 (오래 걸림)
  나눠서: python tools/rebuild_unit_prices.py part 2020-01 2020-06 <작업폴더>   (여러 번, 동시에 돌려도 됨)
          python tools/rebuild_unit_prices.py combine <작업폴더>            → 합치고 날 단위 오류를 뺀 뒤 저장
결과: <FARMBID_OUT>/price_unit_daily.csv (전 기간, 덮어씀) · <DATA>/tables/code_day_domestic.csv (매일 갱신이 앞뒤를 볼 기록)
      <작업폴더>/day_errors.csv (뺀 코드-날 목록)
build_tables.py 의 price_unit_daily 와 같은 계산: 달마다 원장 → 줄 단위 입력 오류 거르기(drop_entry_errors) → 산지를 아는 국산 줄
→ 날 단위 오류(day_errors, 전 기간 앞뒤 30일로 판단) 코드-날 빼기 → (품목코드·품종코드·달)로 단위에 붙여 그날 전국 금액 합 ÷ 물량 합.
price_daily · price_origin_daily 는 건드리지 않음. DB 에 넣을 때는 표를 비우고 넣는다: NC_REPLACE=price_unit_daily python load_db.py
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_tables as B  # noqa: E402


def part(m1, m2, work):
    """달마다: 국산 코드-날 표 + (날·단위·코드) 물량·금액 → work/part_<m1>_*.csv.gz"""
    m = dt.date.fromisoformat(m1 + '-01'); end = dt.date.fromisoformat(m2 + '-01')
    it = B.ref('item')
    uc = B.ref('variety_unit_code')
    uc['months'] = uc.months.map(lambda s: [int(x) for x in s.split(',')] if s else list(range(1, 13)))
    uc = uc.explode('months').rename(columns={'months': 'month'}); uc['month'] = uc.month.astype(int)
    rid = dict(zip(B.ref('region').name, B.ref('region').region_id))
    cds, units = [], []
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
            cds.append(B.code_day(dom))
            dom['month'] = pd.to_datetime(dom.date).dt.month
            j = dom.merge(uc, on=['code4', 'variety_code', 'month'], how='inner')
            units.append(j.groupby(['date', 'unit_id', 'code4', 'variety_code'], as_index=False).agg(volume_kg=('총물량', 'sum'), amount_won=('총금액', 'sum')))
        print(f'{m:%Y-%m} 끝', flush=True)
        m = nxt
    Path(work).mkdir(parents=True, exist_ok=True)
    if cds:
        pd.concat(cds).to_csv(Path(work) / f'part_{m1}_code_day.csv.gz', index=False, compression='gzip')
        pd.concat(units).to_csv(Path(work) / f'part_{m1}_unit_code.csv.gz', index=False, compression='gzip')


def combine(work):
    w = Path(work)
    dt_ = {'code4': str, 'variety_code': str}
    cd = pd.concat(pd.read_csv(f, dtype=dt_) for f in sorted(w.glob('part_*_code_day.csv.gz'))).drop_duplicates(['date', 'code4', 'variety_code'], keep='last')
    uu = pd.concat(pd.read_csv(f, dtype=dt_) for f in sorted(w.glob('part_*_unit_code.csv.gz'))).drop_duplicates(['date', 'unit_id', 'code4', 'variety_code'], keep='last')
    bad = B.day_errors(cd)
    bad.to_csv(w / 'day_errors.csv', index=False)
    key = set(zip(bad.date, bad.code4, bad.variety_code))
    hit = pd.Series([k in key for k in zip(uu.date, uu.code4, uu.variety_code)], index=uu.index)
    print(f'날 단위 오류 코드-날 {len(key)}개 · 단위 가격에서 뺀 물량 {uu.volume_kg[hit].sum() / 1000:,.1f}t ({uu.volume_kg[hit].sum() / uu.volume_kg.sum() * 100:.4f}%)')
    g = uu[~hit].groupby(['date', 'unit_id'], as_index=False).agg(volume_kg=('volume_kg', 'sum'), amount_won=('amount_won', 'sum'))
    g['price'] = (g.amount_won / g.volume_kg).round().astype('Int64')
    g['volume_kg'] = g.volume_kg.round(1); g['amount_won'] = g.amount_won.round()
    g = g.sort_values(['date', 'unit_id'])
    B.save(g[['date', 'unit_id', 'volume_kg', 'amount_won', 'price']], 'price_unit_daily', True)
    cd.sort_values(['date', 'code4', 'variety_code']).to_csv(B.CODE_DAY_FILE, index=False)
    print(f'price_unit_daily {len(g):,}줄 → {B.OUT} · 기록 {B.CODE_DAY_FILE}')


if __name__ == '__main__':
    if sys.argv[1] == 'part':
        part(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == 'combine':
        combine(sys.argv[2])
    else:
        tmp = Path(B.OUT) / '_rebuild_work'
        part(sys.argv[1], sys.argv[2], tmp)
        combine(tmp)
