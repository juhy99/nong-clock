#!/usr/bin/env python3
"""서버(docker compose 의 weather-collector)용 시간표 실행기. 리눅스 cron 대신 이 파일이 run.py 를 정해진 시각에 부른다.

  예보        02·05·08·11·14·17·20·23시 20분   run.py collect --only fcst             (README 3번 시간표와 같음)
  관측·전처리  매일 10:40                       run.py all --only asos,aws,agri,longrange

- 컨테이너가 켜질 때(서버 재부팅·자동 배포): 예보는 바로 한 번 받는다 (24시간 안의 놓친 발표를 다시 받음).
  관측은 마지막 전처리 성공이 26시간보다 오래됐으면 바로 한 번. 처음 켜진 빈 데이터 폴더(raw/ 없음)에서는 아무것도 바로 하지 않는다
  → 그 사이에 PC 에서 받은 원본을 옮기거나 backfill 을 직접 실행 (deploy/README.md "날씨 수집기").
- 같은 작업이 아직 돌고 있으면 그 회차는 건너뛴다. 예보와 관측은 같이 돌 수 있다 (run.py 가 수집기별로 잠금).
- data/HOLD 파일이 있으면 아무 작업도 시작하지 않는다 (원본을 옮기는 동안 잠시 멈출 때).
- 시각은 한국시간. 바꿀 때는 환경변수 WEATHER_FCST_AT ("02:20,05:20,…"), WEATHER_DAILY_AT ("10:40").
"""
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KST = dt.timezone(dt.timedelta(hours=9))
TICK = 20           # 확인 간격(초)
LATE_OK = 30 * 60   # 정해진 시각에서 이만큼 늦은 것까지는 실행 (컨테이너가 잠깐 멈췄던 경우)
DAILY_STALE = 26 * 3600


def parse_times(text):
    return [tuple(int(x) for x in t.strip().split(":")) for t in text.split(",") if t.strip()]


JOBS = {
    "fcst": {"args": ["collect", "--only", "fcst"],
             "at": parse_times(os.getenv("WEATHER_FCST_AT", "02:20,05:20,08:20,11:20,14:20,17:20,20:20,23:20"))},
    "daily": {"args": ["all", "--only", "asos,aws,agri,longrange"], "at": parse_times(os.getenv("WEATHER_DAILY_AT", "10:40"))},
}


def now():
    return dt.datetime.now(KST)


def data_dir():
    p = Path(os.getenv("DATA_DIR") or "data")
    return (p if p.is_absolute() else HERE / p).resolve()


def say(msg):
    print(f"{now():%m-%d %H:%M:%S} [시간표] {msg}", flush=True)


def latest_slot(at, t):
    """t 이전의 가장 최근 예정 시각"""
    cands = [dt.datetime.combine(t.date() - dt.timedelta(days=d), dt.time(h, m), KST) for d in (0, 1) for h, m in at]
    return max(c for c in cands if c <= t)


def last_ok(log_name):
    try:
        runs = json.loads((data_dir() / log_name).read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError):
        return None
    ok = [r["finished_at"] for r in runs if r.get("ok") and r.get("finished_at")]
    return dt.datetime.fromisoformat(max(ok)) if ok else None


class Runner:
    def __init__(self):
        self.procs = {}

    def running(self, name):
        p = self.procs.get(name)
        return p is not None and p.poll() is None

    def start(self, name, why):
        if (data_dir() / "HOLD").exists():
            say(f"{name}: data/HOLD 파일이 있어 건너뜀 ({why})")
            return
        if self.running(name):
            say(f"{name}: 이전 실행이 아직 돌고 있어 이번 회차는 건너뜀 ({why})")
            return
        say(f"{name} 시작 ({why}): run.py {' '.join(JOBS[name]['args'])}")
        self.procs[name] = subprocess.Popen([sys.executable, "-u", "run.py", *JOBS[name]["args"]], cwd=HERE)

    def reap(self):
        for name, p in list(self.procs.items()):
            if p.poll() is not None:
                say(f"{name} 끝 (종료코드 {p.returncode}{', 기록: data/collect_log.json' if p.returncode else ''})")
                del self.procs[name]

    def stop(self, *_):
        say("멈춤 신호 → 돌고 있는 작업 정리")
        for p in self.procs.values():
            if p.poll() is None:
                p.terminate()
        for p in self.procs.values():
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
        sys.exit(0)


def main():
    runner = Runner()
    signal.signal(signal.SIGTERM, runner.stop)
    signal.signal(signal.SIGINT, runner.stop)
    keys = [k for k in ("KMA_APIHUB_KEY", "DATA_GO_KR_KEY") if not os.getenv(k, "").strip()]
    say("켜짐 · 예보 " + ",".join(f"{h:02d}:{m:02d}" for h, m in JOBS["fcst"]["at"])
        + " · 관측·전처리 " + ",".join(f"{h:02d}:{m:02d}" for h, m in JOBS["daily"]["at"])
        + (f" · 키 없음: {', '.join(keys)} (서버 .env 확인, 그 키를 쓰는 수집은 건너뜀)" if keys else ""))

    t = now()
    done = {name: latest_slot(job["at"], t) for name, job in JOBS.items()}   # 지난 회차는 다시 안 함
    if not (data_dir() / "raw").exists():
        say("처음 켜짐(데이터 폴더 비어 있음) → 바로 수집하지 않음. PC 원본을 옮기거나 backfill 을 실행하세요 (deploy/README.md)")
    else:
        runner.start("fcst", "켜질 때 놓친 발표 받기")
        last = last_ok("preprocess_log.json")
        if last is None or (t - last).total_seconds() > DAILY_STALE:
            runner.start("daily", f"마지막 전처리 성공 {last:%m-%d %H:%M}" if last else "전처리 성공 기록 없음")

    while True:
        time.sleep(TICK)
        runner.reap()
        t = now()
        for name, job in JOBS.items():
            slot = latest_slot(job["at"], t)
            if slot > done[name]:
                done[name] = slot
                if (t - slot).total_seconds() <= LATE_OK:
                    runner.start(name, f"{slot:%H:%M} 예정")


if __name__ == "__main__":
    main()
