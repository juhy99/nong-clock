"""갱신 실행기 (11-17): 단계들을 차례로 돌리고 기록한다. 한 번에 하나만.

- start(job) 은 바로 돌아오고, 실제 일은 뒤에서(스레드) 돈다. 이미 돌고 있으면 Busy
- 단계 = 하위 프로세스(argv) 또는 파이썬 함수(call). must_succeed=False 면 실패해도 다음 단계로
- 기록: <log_dir>/updater_runs.json (최근 50개) · 단계 출력 <log_dir>/updater/<시각>_<job>.txt
- 인증키 값은 기록·출력 어디에도 남기지 않음 (mask)
- 실행 도중 컨테이너가 꺼졌으면, 다음에 켤 때 그 실행을 '중단됨'으로 고쳐 둠 (영원히 '실행 중'으로 남지 않게)
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, Mapping, NamedTuple

STEP_TIMEOUT = 3 * 3600   # 한 단계 최대 3시간
KEEP_RUNS = 50
TAIL_LINES = 15
SECRET_NAME = re.compile(r"(_KEY$|_ID$|SECRET|TOKEN|PASSWORD)", re.I)


class Step(NamedTuple):
    name: str
    argv: list[str] | None = None
    cwd: Path | None = None
    env: dict = {}
    must_succeed: bool = True
    call: Callable[[], str] | None = None


class Busy(Exception):
    def __init__(self, job: str, step: str):
        super().__init__(f"이미 갱신 중이에요 ({job} · {step})")
        self.job, self.step = job, step


def mask(text: str, env: Mapping[str, str]) -> str:
    """환경 변수 중 키·아이디·비밀번호 값이 글 속에 있으면 *** 로 (4글자 미만 값은 다른 글자와 겹쳐서 가리지 않음)"""
    for k, v in env.items():
        if v and len(v) >= 4 and SECRET_NAME.search(k):
            text = text.replace(v, "***")
    return text


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Runner:
    def __init__(self, data: Path, log_dir: Path, steps: dict[str, list[Step]], env: Mapping[str, str] | None = None):
        self.data, self.log_dir, self.steps = Path(data), Path(log_dir), steps
        self.env = dict(os.environ if env is None else env)
        self.step_timeout = STEP_TIMEOUT
        self._lock = threading.Lock()
        self._running: dict | None = None
        self._thread: threading.Thread | None = None
        self._runs_file = self.log_dir / "updater_runs.json"
        runs = self._load()
        if any(r.get("finished_at") is None for r in runs):   # 지난번에 돌다가 꺼짐
            for r in runs:
                if r.get("finished_at") is None:
                    r.update(finished_at=_now(), ok=False, status="interrupted", tail=["실행 도중 갱신 서비스가 꺼졌어요"])
            self._save(runs)

    # ── 기록 ──
    def _load(self) -> list[dict]:
        try:
            return json.loads(self._runs_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _save(self, runs: list[dict]) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        tmp = self._runs_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(runs[:KEEP_RUNS], ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self._runs_file)

    def history(self, n: int = 20) -> list[dict]:
        return self._load()[:n]

    def running(self) -> dict | None:
        r = self._running
        return dict(r) if r else None

    def wait(self, timeout: float) -> None:
        if self._thread:
            self._thread.join(timeout)

    # ── 실행 ──
    def start(self, job: str) -> dict:
        if job not in self.steps:
            raise KeyError(job)
        with self._lock:
            if self._running:
                raise Busy(self._running["job"], self._running["step"])
            started = _now()
            self._running = {"job": job, "step": self.steps[job][0].name if self.steps[job] else "", "started_at": started, "line": ""}
            runs = self._load()
            runs.insert(0, {"job": job, "started_at": started, "finished_at": None, "ok": None, "status": "running", "failed_step": None, "tail": []})
            self._save(runs)
        self._thread = threading.Thread(target=self._work, args=(job, started), daemon=True)
        self._thread.start()
        return {"job": job, "started_at": started}

    def _work(self, job: str, started: str) -> None:
        out_dir = self.log_dir / "updater"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{started.replace('-', '').replace(':', '').replace('T', '_')}_{job}.txt"
        status, failed, tail = "ok", None, []
        try:
            with out_file.open("w", encoding="utf-8") as f:
                for st in self.steps[job]:
                    self._running.update(step=st.name, line="")
                    f.write(f"\n===== {st.name} ({_now()}) =====\n"); f.flush()
                    ok, last = self._run_step(st, f)
                    if not ok:
                        f.write(f"[실패] {st.name}{'' if st.must_succeed else ' — 받은 자료로 계속'}\n"); f.flush()
                        if st.must_succeed:
                            status, failed, tail = "failed", st.name, last
                            break
        except Exception as e:   # 기록 파일을 못 쓰는 등
            status, failed, tail = "failed", self._running.get("step") if self._running else None, [mask(f"{type(e).__name__}: {e}", self.env)]
        finally:
            runs = self._load()
            for r in runs:
                if r.get("started_at") == started and r.get("job") == job:
                    r.update(finished_at=_now(), ok=status == "ok", status=status, failed_step=failed, tail=tail, output=out_file.name)
            self._save(runs)
            self._running = None

    def _run_step(self, st: Step, f) -> tuple[bool, list[str]]:
        """한 단계 실행. 출력은 나오는 대로 (키를 가려서) 파일에 쓰고, 끝 15줄을 돌려줌. 진행 중 마지막 줄은 running()['line'] 로 보임"""
        env = {**self.env, **st.env}
        last: deque[str] = deque(maxlen=TAIL_LINES)

        def emit(text: str) -> None:
            for ln in mask(text, env).splitlines():
                f.write(ln + "\n")
                if ln.strip():
                    last.append(ln.rstrip()[:500])
                    if self._running is not None:
                        self._running["line"] = ln.strip()[:160]
            f.flush()

        if st.call is not None:
            try:
                emit(str(st.call() or ""))
                return True, list(last)
            except Exception as e:
                emit(f"{type(e).__name__}: {e}")
                return False, list(last)
        try:
            p = subprocess.Popen(st.argv, cwd=st.cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1, start_new_session=os.name != "nt")
        except OSError as e:
            emit(f"{type(e).__name__}: {e}")
            return False, list(last)
        timed_out = threading.Event()

        def stop() -> None:   # 시간 초과: 이 단계가 띄운 하위 프로세스까지 같이 멈춤
            timed_out.set()
            try:
                os.killpg(p.pid, signal.SIGKILL) if os.name != "nt" else p.kill()
            except OSError:
                pass

        timer = threading.Timer(self.step_timeout, stop)
        timer.start()
        try:
            for ln in p.stdout:
                emit(ln)
            code = p.wait()
        finally:
            timer.cancel()
        if timed_out.is_set():
            emit(f"[시간 초과] {self.step_timeout / 3600:g}시간 넘게 걸려 멈췄어요")
            return False, list(last)
        return code == 0, list(last)
