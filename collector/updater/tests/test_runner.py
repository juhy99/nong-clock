import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import Busy, Runner, Step, mask  # noqa: E402

PY = sys.executable


def py(code):
    return [PY, "-c", code]


def make(tmp_path, steps):
    return Runner(tmp_path, tmp_path / "log", steps, env={"PATH": __import__("os").environ.get("PATH", ""), "MAFRA_API_KEY": "abc123SECRET"})


def test_runs_steps_in_order_and_records_ok(tmp_path):
    r = make(tmp_path, {"daily": [Step("하나", py("print('first')")), Step("둘", py("print('second')"))]})
    r.start("daily"); r.wait(20)
    h = r.history()[0]
    assert h["status"] == "ok" and h["ok"] is True and h["finished_at"] and r.running() is None
    out = (tmp_path / "log" / "updater" / h["output"]).read_text(encoding="utf-8")
    assert out.index("first") < out.index("second") and "===== 하나" in out


def test_second_start_while_running_raises_busy(tmp_path):
    r = make(tmp_path, {"daily": [Step("느린 단계", py("import time; time.sleep(2)"))], "monthly": [Step("x", py("pass"))]})
    r.start("daily")
    with pytest.raises(Busy) as e:
        r.start("monthly")
    assert e.value.job == "daily" and e.value.step == "느린 단계" and "이미 갱신 중" in str(e.value)
    assert r.running()["job"] == "daily"
    r.wait(20)
    r.start("monthly"); r.wait(20)   # 끝난 뒤에는 다시 됨
    assert r.history()[0]["job"] == "monthly"


def test_failed_required_step_stops_and_records_tail(tmp_path):
    marker = tmp_path / "third_ran"
    r = make(tmp_path, {"daily": [Step("하나", py("print('ok')")),
                                  Step("둘", py("import sys; [print('line', i) for i in range(40)]; sys.exit(3)")),
                                  Step("셋", py(f"open(r'{marker}', 'w').write('x')"))]})
    r.start("daily"); r.wait(20)
    h = r.history()[0]
    assert h["status"] == "failed" and h["failed_step"] == "둘" and not marker.exists()
    assert 0 < len(h["tail"]) <= 15 and h["tail"][-1] == "line 39"


def test_optional_step_failure_continues(tmp_path):
    r = make(tmp_path, {"daily": [Step("수집", py("import sys; sys.exit(1)"), must_succeed=False), Step("다음", py("print('went on')"))]})
    r.start("daily"); r.wait(20)
    h = r.history()[0]
    assert h["status"] == "ok"
    assert "went on" in (tmp_path / "log" / "updater" / h["output"]).read_text(encoding="utf-8")


def test_call_step_runs_function_and_exception_fails(tmp_path):
    def boom():
        raise ValueError("파일이 없어요")
    r = make(tmp_path, {"a": [Step("함수", call=lambda: "함수가 돌았음")], "b": [Step("터짐", call=boom)]})
    r.start("a"); r.wait(20)
    assert r.history()[0]["status"] == "ok"
    r.start("b"); r.wait(20)
    h = r.history()[0]
    assert h["status"] == "failed" and h["failed_step"] == "터짐" and "파일이 없어요" in h["tail"][-1]


def test_unfinished_run_marked_interrupted_on_start(tmp_path):
    log = tmp_path / "log"; log.mkdir()
    (log / "updater_runs.json").write_text(json.dumps([{"job": "daily", "started_at": "2026-11-17T06:00:00", "finished_at": None, "status": "running"}]), encoding="utf-8")
    r = make(tmp_path, {"daily": []})
    h = r.history()[0]
    assert h["status"] == "interrupted" and h["finished_at"] and h["ok"] is False


def test_mask_hides_key_values(tmp_path):
    assert mask("key=abc123SECRET", {"MAFRA_API_KEY": "abc123SECRET"}) == "key=***"
    assert mask("id=ab", {"KAMIS_ID": "ab"}) == "id=ab"            # 4글자 미만은 그대로
    assert mask("path=/usr/bin", {"PATH": "/usr/bin"}) == "path=/usr/bin"   # 키가 아닌 변수는 그대로
    r = make(tmp_path, {"daily": [Step("키 찍기", py("import sys; print('serviceKey=abc123SECRET'); sys.exit(2)"))]})
    r.start("daily"); r.wait(20)
    h = r.history()[0]
    assert "abc123SECRET" not in json.dumps(h, ensure_ascii=False)
    assert "abc123SECRET" not in (tmp_path / "log" / "updater" / h["output"]).read_text(encoding="utf-8")


def test_output_streams_while_running_and_shows_last_line(tmp_path):
    r = make(tmp_path, {"daily": [Step("천천히", py("import time; print('kamis 받는 중', flush=True); time.sleep(1.5); print('끝')"))]})
    r.start("daily"); time.sleep(0.8)
    assert r.running()["line"] == "kamis 받는 중"                     # 단계가 끝나기 전에도 보임
    assert "kamis 받는 중" in next((tmp_path / "log" / "updater").glob("*.txt")).read_text(encoding="utf-8")
    r.wait(20)
    assert r.history()[0]["status"] == "ok"


def test_step_timeout_kills_and_fails(tmp_path):
    r = make(tmp_path, {"daily": [Step("멈춘 단계", py("import time; print('시작', flush=True); time.sleep(30)")), Step("다음", py("print('x')"))]})
    r.step_timeout = 1
    t0 = time.time(); r.start("daily"); r.wait(20)
    h = r.history()[0]
    assert time.time() - t0 < 10 and h["status"] == "failed" and h["failed_step"] == "멈춘 단계" and "시간 초과" in h["tail"][-1]
