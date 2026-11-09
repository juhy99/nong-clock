# -*- coding: utf-8 -*-
"""받아 둔 KAMIS 일별 가격 CSV(02_KAMIS_가격_1996_2026/00_KAMIS_일별_소매가격.csv 등)를
collect.py kamis 와 같은 모양(data/raw/kamis/YYYYMMDD.csv)으로 나눈다 — API 키 없이 과거 소매가를 채울 때 (11-09 추가)
  python tools/import_kamis_csv.py <KAMIS_CSV> [시작일 YYYY-MM-DD]
  예) python tools/import_kamis_csv.py "D:\\nong-clock-data\\02_전처리\\02_KAMIS_가격_1996_2026\\00_KAMIS_일별_소매가격.csv" 2025-01-01
끝나면: python build_tables.py --since 2025-01-01 --only retail_price_daily
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C

FIELDS = ['조회일자', '가격구분', '부류코드', '품목코드', '품목명', '품종코드', '품종명', '등급코드', '등급', '단위', '가격']
src = Path(sys.argv[1]); since = sys.argv[2] if len(sys.argv) > 2 else '2020-01-01'
k = pd.read_csv(src, dtype=str, usecols=FIELDS)
k = k[k.조회일자 >= since]
out = C.RAW / 'kamis'; out.mkdir(parents=True, exist_ok=True)
n = 0
for d, g in k.groupby('조회일자'):
    f = out / f"{d.replace('-', '')}.csv"
    if f.exists():   # 이미 API 로 받은 날이면 그 파일에 없는 가격구분만 더함
        old = pd.read_csv(f, dtype=str)
        g = pd.concat([old, g[~g.가격구분.isin(old.가격구분.unique())]])
    g[FIELDS].to_csv(f, index=False, encoding='utf-8-sig'); n += 1
print(f'KAMIS {src.name}: {since} 부터 {n}일 → {out}')
