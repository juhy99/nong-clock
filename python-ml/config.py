"""python-ml 공통 설정 (11-11) — DB 접속과 결과 폴더

DB 접속: 환경 변수 PGHOST · PGPORT · PGDATABASE · PGUSER · PGPASSWORD (없으면 저장소 .env 의 DB_PASSWORD, localhost:5432/farmdb)
결과 폴더: 환경 변수 NC_MODEL_DIR (기본 D:\\nong-clock-data\\05_DB적재\\data\\model) — 패널 스냅샷·성적표·예측을 여기에 둔다 (깃 밖)
"""

import os
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
REF = HERE / "ref"


def _env_file():
    f = REPO / ".env"
    out = {}
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def model_dir() -> Path:
    d = Path(os.getenv("NC_MODEL_DIR", r"D:\nong-clock-data\05_DB적재\data\model"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def connect():
    import psycopg2

    env = _env_file()
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "5432"), dbname=os.getenv("PGDATABASE", "farmdb"),
        user=os.getenv("PGUSER", "postgres"), password=os.getenv("PGPASSWORD", env.get("DB_PASSWORD", "")),
    )


def query(con, sql: str, params: tuple = ()) -> pd.DataFrame:
    cur = con.cursor()
    cur.execute(sql, params)
    cols = [c[0] for c in cur.description] if cur.description else []
    rows = cur.fetchall()
    cur.close()
    return pd.DataFrame(rows, columns=cols)
