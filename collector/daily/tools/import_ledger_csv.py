# -*- coding: utf-8 -*-
"""과거 채우기: 이미 받아 둔 경매원장 월별CSV(mafra_auction.py 결과) → data/raw/auction/YYYYMMDD.csv.gz
API로 2020년부터 다시 받으면 며칠 걸리므로, 조민철 PC의 월별CSV를 그대로 옮겨 쓴다.
  python tools/import_ledger_csv.py <...경매원장_공영도매시장\\월별CSV> 202001 202611
"""
import csv, gzip, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common as C
from collect import AUCTION_KOR

src, m1, m2 = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
cols = list(AUCTION_KOR.values())
out = C.RAW / 'auction'; out.mkdir(parents=True, exist_ok=True)
st = C.state('auction')
for f in sorted(src.glob('*.csv')):
    if not (m1 <= f.stem <= m2):
        continue
    days = {}
    with f.open(encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            days.setdefault(r['정산일자'][:8], []).append({c: r.get(c, '') for c in cols})
    for d, rows in days.items():
        with gzip.open(out / f'{d}.csv.gz', 'wt', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
        st[d] = {m: 'ok' for m in {r['도매시장코드'] for r in rows}}
    print(f'{f.stem}: {len(days)}일', flush=True)
C.save_state('auction', st)
