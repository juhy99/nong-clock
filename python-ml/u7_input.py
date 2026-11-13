"""팀원 일 모델(u7d) 입력 만들기 (11-12) — DB 단위 일별 가격 → 팀원 04 파일과 같은 모양
  python python-ml/u7_input.py <출력 csv.gz>
열: date, 국산_kg, 국산금액_원, 단위, 품목, 묶음, p (= 금액 ÷ 물량). 2020-01-01 부터 DB 마지막 날까지
품목·묶음은 ref/unit_group_team.csv (팀원 05_단위별_모델_출하철_등급_새.csv 의 예측단위·품목·묶음)
DB 단위 가격은 11-12 새 정의(손질·형태·수입 표시 뺌, 만감 두 코드 합침)라 팀원 04 파일과 같은 정의
"""
import sys

import pandas as pd

import config as C

con = C.connect()
d = C.query(con, "SELECT p.date, p.volume_kg, p.amount_won, u.unit_name FROM price_unit_daily p JOIN variety_unit u USING (unit_id) "
                 "WHERE p.date >= '2020-01-01' AND p.volume_kg > 0 ORDER BY u.unit_name, p.date")
g = pd.read_csv(C.REF / "unit_group_team.csv")
d = d.merge(g.rename(columns={"예측단위": "unit_name"}), on="unit_name", how="left")
out = pd.DataFrame({"date": pd.to_datetime(d.date).dt.date, "국산_kg": d.volume_kg.astype(float), "국산금액_원": d.amount_won.astype(float),
                    "단위": d.unit_name, "품목": d.품목, "묶음": d.묶음})
out["p"] = out.국산금액_원 / out.국산_kg
out.to_csv(sys.argv[1], index=False, encoding="utf-8", compression="gzip")
print(f"u7d 입력 → {sys.argv[1]}: {len(out):,}줄 · 단위 {out.단위.nunique()} · {out.date.min()} ~ {out.date.max()} · 품목 빈 단위 {int(out.품목.isna().sum())}")
