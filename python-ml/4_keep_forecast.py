"""4단계: DB 예측 표 정리 (11-12) — price_forecast_daily 에서 오래된 기준일을 지움
남기는 것: 가장 최근 기준일 30개 + 매달 첫 기준일 (한 달 전 예측이 맞았는지 나중에 비교하려고). 그 밖은 지움
  python python-ml/4_keep_forecast.py          (지울 줄 수만 보기)
  python python-ml/4_keep_forecast.py --apply  (실제로 지움)
"""
import sys

import config as C

KEEP_RECENT = 30
con = C.connect()
keep_sql = ("WITH b AS (SELECT DISTINCT base_date FROM price_forecast_daily), "
            "r AS (SELECT base_date FROM b ORDER BY base_date DESC LIMIT %s), "
            "m AS (SELECT min(base_date) AS base_date FROM b GROUP BY date_trunc('month', base_date)) "
            "SELECT base_date FROM r UNION SELECT base_date FROM m")
keep = [r for r, in C.query(con, keep_sql, (KEEP_RECENT,)).itertuples(index=False)]
n = C.query(con, "SELECT count(*) AS n, count(DISTINCT base_date) AS b FROM price_forecast_daily WHERE NOT (base_date = ANY(%s))", (keep,)).iloc[0]
print(f"남길 기준일 {len(keep)}개 · 지울 기준일 {int(n.b)}개 ({int(n.n):,}줄)")
if "--apply" in sys.argv and int(n.n):
    cur = con.cursor(); cur.execute("DELETE FROM price_forecast_daily WHERE NOT (base_date = ANY(%s))", (keep,)); con.commit()
    print("지움")
