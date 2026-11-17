"""갱신 단계 정의 (11-17) — scripts/매일_예측_갱신.bat · 매달_v4_만들기.bat 과 같은 순서를 컨테이너 안에서.

daily  : 수집(사이트가 쓰는 자료만, 실패해도 계속) → 표 만들기 → DB 넣기 → 예측 만들기·넣기
monthly: 추가 자료(실패해도 계속) → v4 만들기 → 결과를 model/v4 로 → daily 단계들
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from runner import Step

PY = [sys.executable, "-X", "utf8", "-u"]
# [지금 갱신] 이 받는 자료 = 사이트(시세 화면·예측)가 실제로 읽는 것만 (11-17).
#   날씨 관측·예보는 weather-collector 컨테이너가 이미 받음 — 여기서 또 받으면 같은 인증키의 하루 호출 한도를 두 번 쓰고 예보만 40분 넘게 걸림
#   공휴일·aT 출하예약·가락 반입량·환율·수급 정책은 화면·예측 어디에서도 읽지 않음. 전부 받으려면 scripts\매일_예측_갱신.bat (collect.py daily)
COLLECT = [("auction", "경매 정산가격"), ("kamis", "KAMIS 도·소매"), ("warning", "기상특보"), ("sanji", "산지공판장")]


def install_v4(work: Path, data: Path) -> str:
    """v4 결과(01_322_월예측_*.csv)를 data/model/v4 로. 같은 이름이 있으면 처음 한 번만 <이름>_직접만들기전.csv.bak 로 남김"""
    latest = Path(work) / "결과" / "_최신.txt"
    if not latest.is_file():
        raise FileNotFoundError(f"결과 폴더를 못 찾았어요 ({latest})")
    txt = latest.read_text(encoding="utf-8").strip()
    res = Path(txt)
    if not res.is_dir():   # 윈도우 bat 이 쓴 경로일 때: 마지막 폴더 이름만 써서 작업 폴더 안에서 찾음
        res = Path(work) / "결과" / re.split(r"[\\/]", txt)[-1]
    files = sorted(res.glob("결과_기준*/01_322_월예측_*.csv"))
    if not files:
        raise FileNotFoundError(f"월 예측 파일이 없어요 ({res})")
    dst = Path(data) / "model" / "v4"
    dst.mkdir(parents=True, exist_ok=True)
    out = []
    for f in files:
        t, bak = dst / f.name, dst / f"{f.stem}_직접만들기전.csv.bak"
        if t.exists() and not bak.exists():
            shutil.copy2(t, bak)
        shutil.copy2(f, t)
        out.append(f"넣음: {t}")
    return "\n".join(out)


def steps(app: Path, data: Path) -> dict[str, list[Step]]:
    app, data = Path(app), Path(data)
    col, work = app / "collector" / "daily", data / "v4_작업"
    base = {"FARMBID_DATA": str(data), "NC_DATA_ROOT": str(data.parent.parent), "PYTHONIOENCODING": "utf-8"}
    tables = {**base, "FARMBID_OUT": str(data / "tables_daily")}
    daily = [Step(f"자료 받기 · {label}", PY + ["collect.py", name], col, base, must_succeed=False) for name, label in COLLECT] + [
        Step("DB 표 만들기", PY + ["build_tables.py"], col, tables),
        Step("DB 에 넣기", PY + ["load_db.py", "--init"], col, tables),
        Step("예측 만들기", PY + [str(app / "python-ml" / "run_daily.py")], app, base),
    ]
    monthly = [
        Step("추가 자료 받기", PY + ["collect_monthly.py", "all"], col, base, must_succeed=False),
        Step("월 예측(v4) 만들기", PY + ["model/run_model.py", "monthly", "--raw", str(data / "raw" / "auction"), "--data", str(work)], col, base),
        Step("월 예측 넣기", call=lambda: install_v4(work, data)),
    ] + daily
    return {"daily": daily, "monthly": monthly}
