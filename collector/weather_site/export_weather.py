"""날씨 화면 파일 만들기: 날씨 대통합 표(관측 CSV) → 화면이 읽는 작은 JSON.

CSV 는 100MB 가 넘어 화면이 그대로 받기엔 커서, 홈 날씨에 쓰는 시·도 부분만 골라 data/ 에 쓴다.
  regions-daily.json    시·도 17곳 최근 120일 일별 관측 + 그 날의 평년값 (최근 날씨 그래프, 평년 대비, 주의 신호)
  regions-monthly.json  시·도 17곳 최근 25개월(다 끝난 달) 월별 관측 + 평년(1991~2020) 월값
  meta.json             만든 시각, 원본 파일 시각, 구분별 기간·행 수, 오류 (관리자 › 데이터 수집)
  collect_log.json · preprocess_log.json   날씨 수집기(collector/weather) 기록을 그대로 복사 (관리자 화면용)

  python export_weather.py          한 번 만들기
  python export_weather.py --loop   5분마다 CSV 가 바뀌었는지 보고 바뀌면 다시 만들기 (서버)

입력 (가장 최근에 바뀐 것):
  - 환경변수 WEATHER_CSV: 서버에서는 날씨 수집기가 매일 만드는 site/날씨_대통합_일별.csv
  - input/*.csv (커밋하지 않음): 데이터 담당에게 받은 CSV 를 손으로 넣을 때
형식: v2 날씨_대통합_일별.csv (시도_일·시군구_일, 일별 평년값) 와 v1 날씨_대통합.csv (시도_일·시도_월·시군구_월) 모두 읽는다.
"""
import argparse
import csv
import json
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
INPUT = HERE / "input"
KST = timezone(timedelta(hours=9))
DAILY_DAYS = 120     # 일별 파일 기간 (이번 달 + 지난달 이상)
MONTHLY_MONTHS = 25  # 월별 파일 기간 (작년 같은 달과 비교할 수 있게)
MONTH_COVER = 0.8    # 월값은 그 달 관측일이 80% 이상일 때만 (데이터 담당 기준과 같게)
CHECK_MIN = 5        # --loop 확인 간격
SETTLE_SEC = 120     # 막 바뀐 CSV 는 다 써질 때까지 이만큼 기다렸다 읽는다 (전처리가 파일을 통째로 다시 씀)
LOG_FILES = ("collect_log.json", "preprocess_log.json")

SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
REQUIRED = ["구분", "날짜", "시도", "최고기온", "최저기온", "강수량"]
# 주의 신호·월 일수 기준 (데이터 담당 전처리와 같게): 폭염 33℃ · 영하 0℃ · 비 1mm · 강풍 순간 14m/s
HOT, FROST, RAIN_DAY, GUST = 33, 0, 1, 14
# CSV 열 → 화면 이름 (일별)
DAILY_COLS = {"최고기온": "temp_max", "최저기온": "temp_min", "강수량": "rain_mm", "평균습도": "humidity",
              "일조시간": "sun_hours", "최대순간풍속": "gust", "평년_평균기온": "normal_temp", "평년_강수량": "normal_rain"}
# v1 시도_월 열 → 화면 이름
MONTHLY_COLS = {"평균기온": "temp_avg", "최고기온": "temp_max", "최저기온": "temp_min", "강수량": "rain_mm",
                "고온일수": "hot_days", "영하일수": "frost_days", "강수일수": "rain_days", "강풍일수": "windy_days"}


def now():
    return datetime.now(KST)


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return default


def write_json(path, data):
    """임시 파일에 쓴 뒤 바꿔 끼운다 (쓰다가 멈춰도 기존 파일이 깨지지 않게)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def num(s):
    """'12.345' → 12.3, 빈칸 → None"""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return round(float(s), 1)
    except ValueError:
        return None


def r1(x):
    return None if x is None else round(x, 1)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def find_csv(folder=None, env=True):
    """WEATHER_CSV 와 input/*.csv 중 가장 최근에 바뀐 파일 (없으면 None)"""
    found = list(Path(folder or INPUT).glob("*.csv"))
    if env and os.environ.get("WEATHER_CSV") and Path(os.environ["WEATHER_CSV"]).exists():
        found.append(Path(os.environ["WEATHER_CSV"]))
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def source_info(path):
    st = path.stat()
    return {"file": path.name, "modified_at": datetime.fromtimestamp(st.st_mtime, KST).isoformat(timespec="seconds"), "size": st.st_size}


def scan(path):
    """CSV 를 한 줄씩 읽어 시도_일·시도_월만 모은다 (시군구 행은 세기만). 엑셀로 저장해 BOM 이 붙어 있어도 읽는다"""
    groups = {}  # 구분 → [행 수, 첫 날짜, 끝 날짜]
    daily, monthly = [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader, [])]
        missing = [c for c in REQUIRED if c not in header]
        if missing:
            raise ValueError(f"CSV 에 필요한 열이 없어요: {', '.join(missing)}")
        at = {c: i for i, c in enumerate(header)}
        for row in reader:
            if len(row) < len(header):
                continue
            kind, day = row[at["구분"]].strip(), row[at["날짜"]].strip()
            g = groups.setdefault(kind, [0, day, day])
            g[0] += 1
            g[1], g[2] = min(g[1], day), max(g[2], day)
            if kind in ("시도_일", "시도_월"):
                rec = {c: row[i] for c, i in at.items()}
                (daily if kind == "시도_일" else monthly).append(rec)
    return groups, daily, monthly


def daily_record(r):
    avg = num(r.get("평균기온"))
    if avg is None:  # v2: 평균기온이 빈 곳은 (최고+최저)/2 근사
        avg = num(r.get("평균기온_근사"))
    return {"date": r["날짜"], "temp_avg": avg, **{k: num(r.get(c)) for c, k in DAILY_COLS.items()}}


def month_days(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return ((date(y + m // 12, m % 12 + 1, 1)) - date(y, m, 1)).days


def months_from_daily(rows, last_day):
    """일별 → 다 끝난 달의 월값 (기온은 평균, 비는 합, 일수는 셈). 관측일이 80% 미만인 달은 값 없음"""
    by_month = {}
    for d in rows:
        by_month.setdefault(d["date"][:7], []).append(d)
    done = [m for m in sorted(by_month) if m < last_day[:7] or last_day == f"{m}-{month_days(m):02d}"]
    out = []
    for m in done[-MONTHLY_MONTHS:]:
        ds = [d for d in by_month[m] if d["temp_max"] is not None]
        if len(ds) < MONTH_COVER * month_days(m):
            out.append({"month": m, **{k: None for k in MONTHLY_COLS.values()}})
            continue
        rain = [d["rain_mm"] for d in ds if d["rain_mm"] is not None]
        out.append({
            "month": m,
            "temp_avg": r1(mean(d["temp_avg"] for d in ds)),
            "temp_max": r1(mean(d["temp_max"] for d in ds)),
            "temp_min": r1(mean(d["temp_min"] for d in ds)),
            "rain_mm": r1(sum(rain)) if len(rain) >= MONTH_COVER * month_days(m) else None,
            "hot_days": sum(1 for d in ds if d["temp_max"] >= HOT),
            "frost_days": sum(1 for d in ds if d["temp_min"] is not None and d["temp_min"] < FROST),
            "rain_days": sum(1 for x in rain if x >= RAIN_DAY),
            "windy_days": sum(1 for d in ds if d["gust"] is not None and d["gust"] >= GUST),
        })
    return out


def normals_from_daily(rows):
    """일별 평년값(같은 월·일 ±3일, 1991~2020) → 월 평년: 기온은 평균, 비는 그 달 날짜 합 (2월 29일 제외)"""
    by_md = {}
    for d in rows:
        if d["normal_temp"] is not None and d["date"][5:] != "02-29":
            by_md[d["date"][5:]] = d
    out = {}
    for m in range(1, 13):
        ds = [d for md, d in by_md.items() if int(md[:2]) == m]
        if len(ds) < 28:
            continue
        rain = [d["normal_rain"] for d in ds if d["normal_rain"] is not None]
        out[str(m)] = {"temp_avg": r1(mean(d["normal_temp"] for d in ds)), "rain_mm": r1(sum(rain)) if len(rain) == len(ds) else None}
    return out


def build(groups, daily_rows, monthly_rows, generated_at):
    if not daily_rows:
        raise ValueError("CSV 에 '시도_일' 행이 없어요")
    unknown = sorted({r["시도"] for r in daily_rows} - set(SIDO))
    if unknown:
        raise ValueError(f"모르는 시도 이름: {', '.join(unknown)} (서울·부산·…·제주·세종 약칭이어야 함)")

    by_sido = {s: [] for s in SIDO}
    for r in daily_rows:
        by_sido[r["시도"]].append(daily_record(r))
    for rows in by_sido.values():
        rows.sort(key=lambda d: d["date"])
    last_day = max(r["날짜"] for r in daily_rows)
    first_kept = (date.fromisoformat(last_day) - timedelta(days=DAILY_DAYS - 1)).isoformat()
    daily = {s: [d for d in rows if d["date"] >= first_kept] for s, rows in by_sido.items()}

    if monthly_rows:  # v1: 데이터 담당이 만든 월값·월 평년값을 그대로
        monthly, normals = {s: [] for s in SIDO}, {s: {} for s in SIDO}
        months = sorted({r["날짜"] for r in monthly_rows})
        keep = set(months[-MONTHLY_MONTHS:])
        for r in sorted(monthly_rows, key=lambda r: r["날짜"]):
            if r["시도"] not in monthly:
                continue
            if num(r.get("평년_평균기온")) is not None:
                normals[r["시도"]][str(int(r["날짜"][5:7]))] = {"temp_avg": num(r.get("평년_평균기온")), "rain_mm": num(r.get("평년_강수량"))}
            if r["날짜"] in keep:
                monthly[r["시도"]].append({"month": r["날짜"], **{k: num(r.get(c)) for c, k in MONTHLY_COLS.items()}})
    else:  # v2: 일별에서 계산
        monthly = {s: months_from_daily(rows, last_day) for s, rows in by_sido.items()}
        normals = {s: normals_from_daily(rows) for s, rows in by_sido.items()}
    last_month = max((m[-1]["month"] for m in monthly.values() if m), default=None)

    return (
        {"generated_at": generated_at, "last_date": last_day, "days": DAILY_DAYS, "regions": daily},
        {"generated_at": generated_at, "last_month": last_month, "normal_period": "1991~2020", "regions": monthly, "normals": normals},
        {"format": "v1" if monthly_rows else "v2", "ranges": {k: [g[1], g[2]] for k, g in sorted(groups.items())},
         "rows": {k: g[0] for k, g in sorted(groups.items())}},
    )


def export(csv_path=None, out=None):
    """CSV 를 읽어 화면 파일을 쓴다. 실패하면 기존 파일은 그대로 두고 meta.json 에 오류만 남긴다"""
    csv_path = Path(csv_path) if csv_path else find_csv()
    out = Path(out or DATA)
    at = now().isoformat(timespec="seconds")
    meta = read_json(out / "meta.json", {})
    meta.pop("tried", None)
    try:
        if not csv_path or not csv_path.exists():
            raise FileNotFoundError("입력 파일이 없어요: 날씨 수집기가 아직 표를 안 만들었거나 (서버: 매일 10:40 이후), "
                                    "collector/weather_site/input 에 데이터 담당 CSV 가 없어요")
        src = meta["tried"] = source_info(csv_path)
        daily, monthly, info = build(*scan(csv_path), at)
        old_last = (meta.get("ranges") or {}).get("시도_일", [None, None])[1] if meta.get("ok") else None
        if old_last and info["ranges"]["시도_일"][1] < old_last and meta.get("source", {}).get("file") == src["file"]:
            raise ValueError(f"새 CSV 의 마지막 날({info['ranges']['시도_일'][1]})이 지난번({old_last})보다 앞이에요 · 덜 써진 파일일 수 있어 그대로 둠")
        write_json(out / "regions-daily.json", daily)
        write_json(out / "regions-monthly.json", monthly)
        meta = {"ok": True, "error": None, "generated_at": at, "checked_at": at, "source": src, "tried": src, **info}
    except Exception as e:  # noqa: BLE001 — 어떤 오류든 화면(관리자)에 보이게 남긴다
        meta = {**meta, "ok": False, "error": str(e), "checked_at": at}
    write_json(out / "meta.json", meta)
    return meta


def changed(csv_path=None, out=None, settle=0):
    """마지막으로 읽어 본 뒤 CSV 가 바뀌었는지 (실패한 파일은 바뀔 때까지 다시 안 읽음). 막 바뀐 파일(settle 초 안)은 다 써질 때까지 기다린다"""
    csv_path = Path(csv_path) if csv_path else find_csv()
    if not csv_path or not csv_path.exists():
        return True  # 없다는 기록(meta.json)만 새로 씀
    if settle and time.time() - csv_path.stat().st_mtime < settle:
        return False
    return source_info(csv_path) != read_json(Path(out or DATA) / "meta.json", {}).get("tried")


def copy_logs(out=None, log_dir=None):
    """날씨 수집기 기록(collect_log.json·preprocess_log.json)을 화면 폴더로 복사 (바뀐 것만)"""
    log_dir = log_dir or os.environ.get("WEATHER_LOG_DIR")
    if not log_dir:
        return 0
    out, n = Path(out or DATA), 0
    for name in LOG_FILES:
        src, dst = Path(log_dir) / name, out / name
        if src.exists() and (not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime):
            out.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".tmp")
            shutil.copy2(src, tmp)
            os.replace(tmp, dst)
            n += 1
    return n


def print_meta(m):
    if m["ok"]:
        r = m["ranges"].get("시도_일") or ["-", "-"]
        print(f"✓ {m['generated_at']}  {m['source']['file']} ({m['format']}) → data/  시도_일 {r[0]} ~ {r[1]}", flush=True)
    else:
        print(f"✗ {m['checked_at']}  {m['error']}", flush=True)


def main():
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔·파일로 돌릴 때 한글·기호가 깨져 멈추지 않게
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description="팜비드 날씨 화면 파일 만들기 (날씨 대통합 CSV → data/*.json)")
    p.add_argument("--loop", action="store_true", help=f"{CHECK_MIN}분마다 CSV 가 바뀌었는지 보고 다시 만들기")
    args = p.parse_args()
    if not args.loop:
        copy_logs()
        m = export()
        print_meta(m)
        sys.exit(0 if m["ok"] else 1)
    last_error = None
    while True:
        copy_logs()
        if changed(settle=SETTLE_SEC):
            m = export()
            if m["ok"] or m["error"] != last_error:  # 같은 오류는 한 번만 출력
                print_meta(m)
            last_error = m["error"]
        time.sleep(CHECK_MIN * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
