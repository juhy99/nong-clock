"""갱신 서비스 (11-17): 관리자 화면의 [지금 갱신]·[월 예측 만들기]·[PDF 올리기] 를 받아 컨테이너 안에서 실행.

- 도커 내부망에서만 (compose 에서 expose 만, ports 없음). Spring 관리자 API 만 부름
- 모든 요청에 X-Updater-Token 헤더 (= .env UPDATER_TOKEN). 서버에 토큰이 없으면 모든 요청 503 (안 열어 둠)
- GET  /status       상태 (기준일·v4·월보·자료별 결과·실행 중·최근 실행)
- POST /run/daily    지금 갱신        → 202 · 실행 중이면 409
- POST /run/monthly  월 예측 만들기   → 202 · 실행 중/아직 못 만드는 때면 409
- POST /wolbo?name=  월보 PDF (본문 = 파일) → 201 · 400(이름·형식) · 413(50MB 초과)
- 자동 실행: UPDATER_DAILY_AT=06:00 이면 매일 그 시각 뒤 한 번. 비우면 꺼짐 (기본)
"""
from __future__ import annotations

import hmac
import json
import os
import threading
import time
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jobs
import state
from runner import Busy, Runner

PORT = 8090


def parse_at(at: str | None) -> str | None:
    """'6:00' · '06:00' → '06:00'. 비었거나 잘못 쓰면 None (= 자동 실행 꺼짐)"""
    try:
        h, m = (int(x) for x in (at or "").strip().split(":"))
        return f"{h:02d}:{m:02d}" if 0 <= h < 24 and 0 <= m < 60 else None
    except ValueError:
        return None


def due(now: datetime, at: str | None, last_daily_date: date | None) -> bool:
    """자동 실행할 때인가: 시각이 정해져 있고, 그 시각이 지났고, 오늘 아직 안 돌았으면"""
    at = parse_at(at)
    return bool(at) and now.strftime("%H:%M") >= at and last_daily_date != now.date()


def last_daily_date(runner: Runner) -> date | None:
    """매일 갱신이 마지막으로 시작된 날 (월 예측도 매일 단계를 포함하므로 같이 셈)"""
    for r in runner.history(50):
        try:
            return datetime.fromisoformat(r["started_at"]).date()
        except (KeyError, ValueError, TypeError):
            continue
    return None


def make_server(port: int, token: str, runner: Runner, data: Path, seed_dir: Path, clock=datetime.now, schedule: str | None = None) -> ThreadingHTTPServer:
    token, schedule = (token or "").strip(), parse_at(schedule)

    class H(BaseHTTPRequestHandler):
        server_version, sys_version, protocol_version = "updater", "", "HTTP/1.1"

        def log_message(self, fmt, *args):   # 접근 기록은 짧게 (토큰·본문 없음)
            print(f"[{datetime.now():%m-%d %H:%M:%S}] {self.command} {urlparse(self.path).path} → {args[1] if len(args) > 1 else ''}", flush=True)

        def send(self, code: int, body: dict):
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(raw)

        def guard(self) -> bool:
            if not token:
                self.close_connection = True
                self.send(503, {"message": "UPDATER_TOKEN 이 설정되지 않았어요 (.env)"})
                return False
            if not hmac.compare_digest((self.headers.get("X-Updater-Token") or "").encode(), token.encode()):
                self.close_connection = True
                self.send(401, {"message": "허용되지 않은 요청이에요"})
                return False
            return True

        def do_GET(self):
            if not self.guard():
                return
            if urlparse(self.path).path != "/status":
                return self.send(404, {"message": "없는 주소예요"})
            st = state.status(data, seed_dir, clock().date())
            hist = runner.history(10)
            st.update(running=runner.running(), history=hist, schedule=schedule, alerts=state.alerts(data, st, hist, clock()))
            self.send(200, st)

        def do_POST(self):
            if not self.guard():
                return
            u = urlparse(self.path)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if u.path == "/wolbo":
                if n < 0 or n > state.WOLBO_MAX:   # 읽지 않고 거절
                    self.close_connection = True
                    return self.send(413, {"message": "파일이 너무 커요 (50MB 까지)"})
                body = self.rfile.read(n)
                try:
                    saved = state.save_wolbo(data, (parse_qs(u.query).get("name") or [""])[0], body)
                except ValueError as e:
                    return self.send(400, {"message": str(e)})
                except OSError as e:
                    return self.send(500, {"message": f"저장하지 못했어요 ({type(e).__name__})"})
                return self.send(201, {"saved": saved})
            if n > 0:
                self.rfile.read(min(n, 1 << 20))
            if u.path in ("/run/daily", "/run/monthly"):
                job = u.path.rsplit("/", 1)[1]
                st = state.status(data, seed_dir, clock().date())
                if not st["data_ok"]:
                    return self.send(409, {"message": "자료 폴더가 연결되지 않았어요 (.env 의 NC_DATA_ROOT)"})
                if job == "monthly" and not st["monthly"]["ready"]:
                    return self.send(409, {"message": st["monthly"]["reason"]})
                try:
                    return self.send(202, runner.start(job))
                except Busy as e:
                    return self.send(409, {"message": str(e)})
            self.send(404, {"message": "없는 주소예요"})

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    srv.daemon_threads = True
    return srv


def schedule_loop(runner: Runner, at: str, clock=datetime.now, every: float = 30, stop: threading.Event | None = None):
    while not (stop and stop.is_set()):
        try:
            if runner.running() is None and due(clock(), at, last_daily_date(runner)):
                print(f"[자동 실행] 매일 갱신 시작 ({at})", flush=True)
                runner.start("daily")
        except Busy:
            pass
        except Exception as e:   # 스케줄이 죽어 서비스가 멈추지 않게
            print(f"[자동 실행 오류] {type(e).__name__}: {e}", flush=True)
        time.sleep(every)


def link_extras(app: Path, data: Path) -> Path:
    """깃에 없는 것(v4 seed · 한글 OCR 자료)을 자료 폴더 v4_seed 에서 가져다 쓰게 연결. seed 폴더 경로를 돌려줌"""
    bundle, daily = data / "v4_seed", app / "collector" / "daily"
    seed, td = daily / "model" / "seed", daily / "tools" / "tessdata"
    pairs = [(seed, [bundle]), (td, [bundle / "tessdata", daily / "tools" / "tessdata_system"])]
    for link, cands in pairs:
        if link.exists():
            continue
        for c in cands:
            if c.is_dir():
                try:
                    link.symlink_to(c, target_is_directory=True)
                except OSError:
                    pass
                break
    return seed if seed.exists() else bundle


def main():
    app = Path(__file__).resolve().parents[2]
    root = Path(os.environ.get("NC_DATA_ROOT") or "/nong-clock-data")
    data = Path(os.environ.get("FARMBID_DATA") or root / "05_DB적재" / "data")
    token, at = os.environ.get("UPDATER_TOKEN", ""), parse_at(os.environ.get("UPDATER_DAILY_AT"))
    seed = link_extras(app, data)
    runner = Runner(data, data / "log", jobs.steps(app, data))
    print(f"갱신 서비스 :{PORT} · 자료 {data} ({'있음' if data.is_dir() else '없음 — NC_DATA_ROOT 확인'}) · 토큰 {'있음' if token.strip() else '없음 — 모든 요청 503'} · 자동 실행 {at or '꺼짐'}", flush=True)
    if at:
        threading.Thread(target=schedule_loop, args=(runner, at), daemon=True).start()
    make_server(PORT, token, runner, data, seed, schedule=at).serve_forever()


if __name__ == "__main__":
    main()
