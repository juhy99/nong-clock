"""갱신 상태 읽기 · 월보 PDF 받기 (11-17). 자료 폴더의 파일만 읽음 — 없으면 None 으로, 예외 없이.

status(): 예측 기준일 · v4 기준월 · 원장 마지막 날 · 자료별 마지막 수집 결과 · 월 예측을 만들 수 있는지 · 이번 달 월보 4종이 있는지
save_wolbo(): 관리자가 올린 월보 PDF 를 data/manual/월보/ 에 (이름·형식·크기 확인)
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

SEED_FILE = "원장_일별_줄오류만_seed.csv.gz"
WOLBO_KINDS = ("VC", "VS", "VPO", "F")           # 엽근채소 · 양념채소 · 감자 · 과일
WOLBO_NAME = re.compile(r"^(VC|VS|VPO|F)(\d{6}).*\.pdf$", re.I)
WOLBO_MAX = 50 * 1024 * 1024
# 상태에 보여 주는 자료 = [지금 갱신] 이 받는 것(jobs.COLLECT) + DB 넣기. 예전 bat 실행이 남긴 다른 자료의 줄은 보이지 않음
SHOWN = ("auction", "kamis", "warning", "sanji", "db_load")
MONTHLY_FROM_DAY = 3                              # run_model.py monthly 와 같은 규칙: 원장 마지막 날이 3일 이후


def _iso(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"


def _latest(folder: Path, pattern: str, rx: str) -> str | None:
    try:
        got = [m.group(1) for p in folder.glob(pattern) if (m := re.search(rx, p.name))]
    except OSError:
        return None
    return max(got) if got else None


def _v4_base(data: Path) -> str | None:
    """run_daily.py 가 고르는 것과 같은 파일(수정 시각이 가장 새 것)의 기준월"""
    try:
        files = sorted((data / "model" / "v4").glob("*월예측*.csv"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return None
    if not files:
        return None
    m = re.search(r"기준(\d{6})", files[-1].name)
    return f"{m.group(1)[:4]}-{m.group(1)[4:]}" if m else None


def _sources(data: Path) -> list[dict]:
    last: dict[str, dict] = {}
    try:
        with (data / "log" / "collect_log.csv").open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("source"):
                    last[row["source"]] = row
    except (OSError, csv.Error, UnicodeDecodeError):
        return []
    return [{"source": s, "ok": str(last[s].get("ok", "")).strip().lower() in ("true", "1", "t"),
             "finished_at": last[s].get("finished_at") or None, "error": (last[s].get("error") or "")[:200] or None}
            for s in SHOWN if s in last]


def _prev_month(y: int, m: int) -> str:
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _monthly(ledger_last: str | None, v4_base: str | None, seed_dir: Path) -> dict:
    if not (Path(seed_dir) / SEED_FILE).is_file():
        return {"ready": False, "reason": "v4 seed 가 없어요 (자료 폴더 v4_seed)", "next_base": None}
    if not ledger_last:
        return {"ready": False, "reason": "경매 원자료가 없어요 (raw/auction)", "next_base": None}
    y, m, d = (int(x) for x in ledger_last.split("-"))
    nb = _prev_month(y, m)
    if v4_base and nb <= v4_base:
        nm = 1 if m == 12 else m + 1
        return {"ready": False, "reason": f"이미 {v4_base} 기준으로 만들었어요 — 다음은 {nm}월 {MONTHLY_FROM_DAY}일부터", "next_base": nb}
    if d < MONTHLY_FROM_DAY:
        return {"ready": False, "reason": f"원장 정산이 다 올라오는 {m}월 {MONTHLY_FROM_DAY}일부터 가능", "next_base": nb}
    return {"ready": True, "reason": f"만들 수 있어요 (기준 {nb})", "next_base": nb}


def _wolbo(data: Path, today: date) -> dict:
    ym = f"{today.year}{today.month:02d}"
    have = {k: False for k in WOLBO_KINDS}
    try:
        for p in (data / "manual" / "월보").iterdir():
            m = WOLBO_NAME.match(p.name)
            if m and m.group(2) == ym:
                have[m.group(1).upper()] = True
    except OSError:
        pass
    return {"month": f"{today.year}-{today.month:02d}", "have": have}


def status(data: Path, seed_dir: Path, today: date) -> dict:
    data = Path(data)
    fb = _latest(data / "model", "forecast_*", r"^forecast_(\d{8})$")
    ll = _latest(data / "raw" / "auction", "*.csv.gz", r"^(\d{8})\.csv\.gz$")
    forecast_base, ledger_last, v4 = (_iso(fb) if fb else None), (_iso(ll) if ll else None), _v4_base(data)
    return {"forecast_base": forecast_base, "v4_base": v4, "ledger_last": ledger_last, "sources": _sources(data),
            "monthly": _monthly(ledger_last, v4, seed_dir), "wolbo": _wolbo(data, today), "data_ok": data.is_dir()}


def save_wolbo(data: Path, filename: str, body: bytes) -> str:
    name = re.split(r"[\\/]", filename or "")[-1].strip()
    if not WOLBO_NAME.match(name):
        raise ValueError("월보 파일 이름이 아니에요. VC·VS·VPO·F 로 시작하고 연월 6자리가 붙은 PDF 여야 해요 (예: VC202611.pdf)")
    if len(body) > WOLBO_MAX:
        raise ValueError("파일이 너무 커요 (50MB 까지)")
    if not body.startswith(b"%PDF-"):
        raise ValueError("PDF 파일이 아니에요 (내용이 PDF 형식이 아님)")
    folder = Path(data) / "manual" / "월보"
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / (name + ".part")
    tmp.write_bytes(body)
    tmp.replace(folder / name)
    return name


# ── 알림: 갱신이 실패했거나 자료가 덜 들어왔을 때 관리자 화면에 띄울 문장 (자동 실행을 켜 두고 아침에 확인하는 용도) ──
SOURCE_NAME = {"auction": "경매 정산가격", "kamis": "KAMIS", "warning": "기상특보", "sanji": "산지공판장", "db_load": "DB 넣기"}
MARKETS_FEW = 16   # 전날 경매 자료가 이 수보다 적은 시장만 올라왔으면 "덜 올라옴" (평소 28~32곳)


def auction_day(data: Path, ymd: str) -> tuple[int, int] | None:
    """그날 경매 정산가격을 받은 시장 수 (ok, 전체). 수집 기록(raw/auction/_state.json)에 그날이 없으면 None"""
    try:
        v = json.loads((Path(data) / "raw" / "auction" / "_state.json").read_text(encoding="utf-8")).get(ymd)
    except (OSError, ValueError):
        return None
    if v is None:
        return None
    if isinstance(v, str):
        return (1, 1) if v == "ok" else (0, 1)
    return sum(1 for x in v.values() if x == "ok"), len(v)


def last_trading_day(today: date) -> date:
    """오늘 전의 가장 가까운 경매일 (일요일은 쉼)"""
    d = today - timedelta(days=1)
    return d - timedelta(days=1) if d.weekday() == 6 else d


def alerts(data: Path, st: dict, history: list[dict], now: datetime) -> list[dict]:
    """[{level: bad|warn, text}] — 급한 것부터. 실행 중일 때는 비움 (끝나면 다시 판단)"""
    if any(h.get("status") == "running" for h in history[:1]):
        return []
    out, md = [], lambda iso: f"{int(iso[5:7])}/{int(iso[8:10])}"
    last = history[0] if history else None
    if last and last.get("status") in ("failed", "interrupted"):
        when = f"{md(last['started_at'])} {last['started_at'][11:16]}"
        why = f"'{last.get('failed_step')}' 단계에서 실패했어요" if last["status"] == "failed" else "도중에 끊겼어요"
        out.append({"level": "bad", "text": f"마지막 갱신({when})이 {why} — [지금 갱신] 을 눌러 주세요"})
    bad = [SOURCE_NAME.get(s["source"], s["source"]) for s in st.get("sources", []) if not s["ok"]]
    if bad and not out:
        out.append({"level": "warn", "text": f"받지 못한 자료가 있어요 ({', '.join(bad)}) — 잠시 뒤 [지금 갱신] 을 다시 눌러 주세요"})
    ran_today = bool(last and str(last.get("started_at", ""))[:10] == now.date().isoformat())
    day = last_trading_day(now.date())
    got = auction_day(data, day.strftime("%Y%m%d"))
    if st.get("data_ok") and (ran_today or got is not None) and not (out and out[0]["level"] == "bad"):
        if got is None or got[0] == 0:
            out.append({"level": "warn", "text": f"{day.month}/{day.day} 경매 자료가 아직 안 올라왔어요 — 오후에 [지금 갱신] 을 다시 눌러 주세요 (휴장일이면 정상)"})
        elif got[0] < MARKETS_FEW:
            out.append({"level": "warn", "text": f"{day.month}/{day.day} 경매 자료가 덜 올라왔어요 (시장 {got[0]}/{got[1]}곳) — 오후에 [지금 갱신] 을 다시 눌러 주세요"})
    fb = st.get("forecast_base")
    if fb and (now.date() - date.fromisoformat(fb)).days > 4:
        out.append({"level": "warn", "text": f"예측 기준일이 {md(fb)} 에 멈춰 있어요 — [지금 갱신] 을 눌러 주세요"})
    return out
