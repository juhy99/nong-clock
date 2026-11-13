"""매일 예측 갱신 (11-12) — DB 에 오늘치 시세가 들어간 뒤 실행 (scripts/매일_예측_갱신.bat 이 수집 다음에 부름)

  python python-ml/run_daily.py              전부
  python python-ml/run_daily.py --from 5     5단계부터 (앞 단계 결과 폴더는 가장 최근 것을 씀)

단계 (결과는 모두 model 폴더 = config.model_dir(), 기본 D:\\nong-clock-data\\05_DB적재\\data\\model):
  1 패널        1_panel.py           DB → panel_<기준일>/          (기준일 = DB 단위 시세 마지막 날)
  2 원인 엔진   2_engine.py          panel → run_<기준일>/forecast_unit_daily.csv.gz (기준일 다음 날부터 365일)
  3 팀원 일     u7_input.py + team/u7d_일주_물량뺌.py   DB → u7_<기준일>/75_최신_일별예측.csv (1~14거래일)
  4 팀원 월     model/v4/ 에서 가장 새 월 예측 파일 (팀원이 매달 주거나, v4 를 직접 돌린 결과를 여기에 둠)
  5 섞기        3_forecast.py        → forecast_<기준일>/price_forecast_daily.csv
  6 DB 넣기     collector/daily/load_db.py --only price_forecast_daily
  7 정리        4_keep_forecast.py --apply  (최근 30개 기준일 + 매달 첫 기준일만 남김)
가격은 기준점(작년 수준·계절 모양)과 정답에만 — 어느 단계도 지금 시세를 입력으로 쓰지 않음
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import config as C

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PY = sys.executable
M = C.model_dir()
start = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 1


def run(step, title, args, cwd=HERE, env=None):
    if step < start:
        return
    t0 = time.time()
    print(f"\n[{step}] {title}\n    {' '.join(str(a) for a in args)}", flush=True)
    subprocess.run([PY, "-X", "utf8", *map(str, args)], cwd=cwd, env={**os.environ, **(env or {})}, check=True)
    print(f"    끝 ({time.time() - t0:.0f}초)", flush=True)


def latest(pattern):
    xs = sorted(M.glob(pattern))
    if not xs:
        sys.exit(f"[멈춤] {M} 에 {pattern} 이 없어요")
    return xs[-1]


run(1, "패널 (DB → 원인 모델 입력)", ["1_panel.py"])
panel = latest("panel_*")
base = panel.name.split("_")[1]
run(2, "원인 엔진 (322단위 × 1~365일)", ["2_engine.py", panel])
u7 = M / f"u7_{base}"; u7.mkdir(exist_ok=True)
run(3, "팀원 일 모델 입력 (DB → u7d 모양)", ["u7_input.py", u7 / "입력.csv.gz"])
run(3, "팀원 일 모델 u7d (1~14거래일)", [HERE / "team" / "u7d_일주_물량뺌.py", u7, u7 / "입력.csv.gz"], cwd=u7)
v4 = sorted((M / "v4").glob("*월예측*.csv"), key=lambda p: p.stat().st_mtime)
if not v4:
    sys.exit(f"[멈춤] {M / 'v4'} 에 팀원 v4 월 예측 파일(01_322_월예측_…csv)이 없어요")
v4 = v4[-1]
print(f"\n[4] 팀원 월 예측: {v4.name}", flush=True)
out = M / f"forecast_{base}"
run(5, "섞기 → 일 단위 예측 표", ["3_forecast.py", "--engine", M / f"run_{base}" / "forecast_unit_daily.csv.gz", "--v4", v4,
                                 "--u7c", u7 / "75_최신_일별예측.csv", "--panel", panel, "--items", REPO / "shared" / "items50.json", "--out", out])
run(6, "DB 넣기 (price_forecast_daily)", ["load_db.py", "--only", "price_forecast_daily"], cwd=REPO / "collector" / "daily", env={"FARMBID_OUT": str(out)})
run(7, "오래된 예측 정리", ["4_keep_forecast.py", "--apply"])
print(f"\n다 끝: 기준일 {base} 예측이 DB 에 들어감 → 화면 /ai", flush=True)
