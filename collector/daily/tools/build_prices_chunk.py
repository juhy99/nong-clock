# -*- coding: utf-8 -*-
"""과거 시세 표를 달 묶음으로 나눠 만들기 (한 번에 다 돌리기 어려운 PC용, 11-09 추가)
  python tools/build_prices_chunk.py 2025-01 2025-06 --first   # 첫 묶음: 표를 새로 씀
  python tools/build_prices_chunk.py 2025-07 2025-12            # 다음 묶음: 이어 씀
끝나면: python build_tables.py --only price_index_daily market_factor
"""
import sys, datetime as dt, warnings
from pathlib import Path
warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import build_tables as B
a1, a2 = sys.argv[1], sys.argv[2]; first = '--first' in sys.argv
m = dt.date.fromisoformat(a1 + '-01'); end = dt.date.fromisoformat(a2 + '-01')
hist = []
while m <= end:
    nxt = (m.replace(day=28) + dt.timedelta(4)).replace(day=1)
    a = B.read_auction(m, nxt)
    if not a.empty:
        B._prices_chunk(a, first, hist); first = False
    print(m.strftime('%Y-%m'), '완료', flush=True)
    m = nxt
if hist:
    B.upsert_hist(pd.concat(hist), 'price_all', ['date', 'market_code', 'item_code'])
