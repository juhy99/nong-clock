# -*- coding: utf-8 -*-
"""받아 둔 기상특보 시·도 일별 표 → weather_warning_daily (11-11 추가, API 키 없이 과거 특보 채우기)
  python tools/import_warning_csv.py <03_특보_시도_일별.csv>
  예) python tools/import_warning_csv.py "D:\\nong-clock-data\\02_전처리\\28_기상특보_이력\\03_특보_시도_일별.csv"
원본 한 줄 = 날짜 × 시도, 특보 종류마다 등급(0 없음·1 주의보·2 경보)과 비중(그 시도 육상 구역 중 걸린 몫).
특보가 걸린(등급 > 0) 칸만 한 줄씩 넣는다. 끝나면: python load_db.py --only weather_warning_daily
"""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C

TYPES = ['호우', '폭염', '한파', '대설', '태풍', '강풍', '건조', '황사']
w = pd.read_csv(sys.argv[1], encoding='utf-8-sig')
rid = pd.read_csv(C.HERE / 'ref' / 'region.csv', dtype=str, encoding='utf-8-sig')
rid = dict(zip(rid.name, rid.region_id))
miss = sorted(set(w.시도) - set(rid))
if miss:
    sys.exit(f'region.csv 에 없는 시도: {miss}')
out = []
for t in TYPES:
    x = w[w[f'{t}_등급'] > 0]
    out.append(pd.DataFrame({'date': x.날짜, 'region_id': x.시도.map(rid), 'warn_type': t,
                             'level': x[f'{t}_등급'].round().astype(int), 'area_share': x[f'{t}_비중'].round(3)}))
o = pd.concat(out).sort_values(['date', 'region_id', 'warn_type'])
o.to_csv(C.OUT / 'weather_warning_daily.csv', index=False, encoding='utf-8')
print(f'weather_warning_daily: {len(o):,}행 ({o.date.min()} ~ {o.date.max()}) → {C.OUT}')
print(o.groupby('warn_type').size().to_string())
