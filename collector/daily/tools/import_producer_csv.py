# -*- coding: utf-8 -*-
"""산지공판장 과거 채우기 (11-12) — 팀 전처리 파일 → producer_price_daily.csv · producer.csv
  python tools/import_producer_csv.py <05_산지공판장_일별_공판장_품목.csv.gz> <01_공판장_위치추정.csv>   → <FARMBID_OUT>/
- 일별 파일: 팀 28_산지공판장_aT신규API_보완 (2020-02 ~ 2026-09-03, 공판장 85곳 × 품목). 50품목만, 전국('national') 줄 더함
- 위치 파일: 팀 107_산지공판장_위치_산지시도 (공판장마다 시·도 · 시·군·구 · 1위 시·도 몫). 공판장 이름으로 붙임 (85곳 모두 맞음)
- 그 뒤 날짜는 매일 수집(collect.py sanji → build_tables producer_price_daily)이 이어 씀. 화면 '산지공판장 가격' 카드용
"""
import sys

import pandas as pd

sys.path.insert(0, __import__('pathlib').Path(__file__).resolve().parents[1].as_posix())
import common as C  # noqa: E402

src, locf = sys.argv[1], sys.argv[2]
d = pd.read_csv(src, dtype={'법인_공판장코드': str, '품목코드4': str})
it = pd.read_csv(C.HERE / 'ref' / 'item.csv', dtype=str)
d['item_code'] = d.품목코드4.map(dict(zip(it.code4, it.item_code)))
d = d[d.item_code.notna() & (d.물량_kg > 0) & (d.금액_원 > 0)]
d = d.rename(columns={'날짜': 'date', '법인_공판장코드': 'producer_code', '법인_공판장명': 'producer_name', '물량_kg': 'volume_kg', '금액_원': 'amount_won'})
nat = d.assign(producer_code='national', producer_name='전국')
g = pd.concat([d, nat]).groupby(['date', 'producer_code', 'producer_name', 'item_code'], as_index=False)[['volume_kg', 'amount_won']].sum()
g['price'] = (g.amount_won / g.volume_kg).round().astype('Int64')
g['volume_kg'] = g.volume_kg.round(1); g['amount_won'] = g.amount_won.round()
C.OUT.mkdir(parents=True, exist_ok=True)
g.to_csv(C.OUT / 'producer_price_daily.csv', index=False, encoding='utf-8')
loc = pd.read_csv(locf)
p = d.groupby('producer_code').producer_name.agg(lambda s: s.mode()[0]).reset_index()
p = p.merge(loc.rename(columns={'법인_공판장명': 'producer_name', '시도': 'sido', '시군구': 'sigungu', '1위시도몫%': 'sido_share_pct'})[['producer_name', 'sido', 'sigungu', 'sido_share_pct']], on='producer_name', how='left')
p.to_csv(C.OUT / 'producer.csv', index=False, encoding='utf-8')
print(f'producer_price_daily: {len(g):,}줄 ({g.date.min()} ~ {g.date.max()}) · producer: {len(p)}곳 (시·도 빈 곳 {int(p.sido.isna().sum())})')
