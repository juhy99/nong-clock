import json
import sys
import threading
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import state  # noqa: E402
from runner import Runner, Step  # noqa: E402
from server import due, make_server, parse_at  # noqa: E402

PY, TOKEN, PDF = sys.executable, "t0ken-for-test", b"%PDF-1.7\n..."


@pytest.fixture
def up(tmp_path):
    made = []

    def _up(token=TOKEN, ledger="20261114", seed=True, data_exists=True):
        d = tmp_path / "data"
        if data_exists:
            for p in (d / "raw" / "auction" / f"{ledger}.csv.gz", d / "model" / "v4" / "01_322_월예측_기준202610_앞으로12달.csv"):
                p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"x")
        if seed:
            (tmp_path / "seed").mkdir(exist_ok=True); (tmp_path / "seed" / state.SEED_FILE).write_bytes(b"x")
        r = Runner(d, tmp_path / "log", {"daily": [Step("느린 단계", [PY, "-c", "import time; time.sleep(1.5)"])], "monthly": [Step("x", [PY, "-c", "pass"])]}, env={})
        srv = make_server(0, token, r, d, tmp_path / "seed", clock=lambda: datetime(2026, 11, 17, 10, 0), schedule="6:00")
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        made.append((srv, r))
        return f"http://127.0.0.1:{srv.server_address[1]}", r, d
    yield _up
    for srv, r in made:
        r.wait(10); srv.shutdown(); srv.server_close()


def call(url, method="GET", token=TOKEN, body=None, headers=None):
    h = dict(headers or {})
    if token is not None:
        h["X-Updater-Token"] = token
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_no_token_401(up):
    url, r, _ = up()
    assert call(url + "/status", token=None)[0] == 401
    assert call(url + "/status", token="wrong")[0] == 401
    assert call(url + "/run/daily", "POST", token="wrong")[0] == 401 and r.running() is None
    assert call(url + "/wolbo?name=VC202611.pdf", "POST", token=None, body=PDF)[0] == 401


def test_server_without_token_503(up):
    url, r, _ = up(token="")
    for tok in (None, "", "anything"):
        code, body = call(url + "/status", token=tok)
        assert code == 503 and "UPDATER_TOKEN" in body["message"]
    assert call(url + "/run/daily", "POST", token="")[0] == 503 and r.running() is None


def test_status_shape(up):
    url, _, _ = up()
    code, st = call(url + "/status")
    assert code == 200
    for k in ("forecast_base", "v4_base", "ledger_last", "sources", "monthly", "wolbo", "data_ok", "running", "history", "schedule", "alerts"):
        assert k in st
    assert st["running"] is None and st["history"] == [] and st["schedule"] == "06:00" and st["wolbo"]["month"] == "2026-11"
    assert TOKEN not in json.dumps(st)
    assert call(url + "/nothing")[0] == 404


def test_run_daily_202_then_409(up):
    url, r, _ = up()
    code, body = call(url + "/run/daily", "POST")
    assert code == 202 and body["job"] == "daily" and body["started_at"]
    code, body = call(url + "/run/daily", "POST")
    assert code == 409 and "이미 갱신 중" in body["message"] and "느린 단계" in body["message"]
    assert call(url + "/status")[1]["running"]["job"] == "daily"
    r.wait(10)
    st = call(url + "/status")[1]
    assert st["running"] is None and st["history"][0]["status"] == "ok"


def test_monthly_not_ready_409_with_reason(up):
    url, r, _ = up()   # 원장 11-14, v4 2026-10 → 이미 만든 달
    code, body = call(url + "/run/monthly", "POST")
    assert code == 409 and "이미 2026-10" in body["message"] and r.running() is None


def test_monthly_ready_202(up):
    url, r, _ = up(ledger="20261204")
    assert call(url + "/run/monthly", "POST")[0] == 202
    r.wait(10)
    assert r.history()[0]["job"] == "monthly"


def test_run_without_data_folder_409(up):
    url, r, _ = up(data_exists=False)
    code, body = call(url + "/run/daily", "POST")
    assert code == 409 and "NC_DATA_ROOT" in body["message"] and r.running() is None
    assert call(url + "/status")[1]["data_ok"] is False


def test_wolbo_upload_201_and_bad_400(up):
    url, _, d = up()
    code, body = call(url + "/wolbo?name=VC202611.pdf", "POST", body=PDF)
    assert code == 201 and body == {"saved": "VC202611.pdf"} and (d / "manual" / "월보" / "VC202611.pdf").read_bytes() == PDF
    assert call(url + "/status")[1]["wolbo"]["have"]["VC"] is True
    for name, b in (("abc.pdf", PDF), ("VC202611.txt", PDF), ("VC202611.pdf", b"hello"), ("", PDF)):
        code, body = call(url + f"/wolbo?name={name}", "POST", body=b)
        assert code == 400 and body["message"]
    code, body = call(url + "/wolbo?name=..%2F..%2FF202611.pdf", "POST", body=PDF)
    assert code == 201 and (d / "manual" / "월보" / "F202611.pdf").exists()


def test_wolbo_too_large_413(up):
    url, _, d = up()
    import http.client
    c = http.client.HTTPConnection("127.0.0.1", int(url.rsplit(":", 1)[1]), timeout=10)
    c.putrequest("POST", "/wolbo?name=VC202611.pdf"); c.putheader("X-Updater-Token", TOKEN); c.putheader("Content-Length", str(state.WOLBO_MAX + 1)); c.endheaders()
    resp = c.getresponse()   # 본문을 보내기 전에 거절
    assert resp.status == 413 and "50MB" in json.loads(resp.read())["message"]
    c.close()
    assert not (d / "manual" / "월보").exists()


def test_schedule_due():
    now, today = datetime(2026, 11, 17, 10, 0), date(2026, 11, 17)
    assert due(now, "06:00", date(2026, 11, 16)) is True and due(now, "06:00", None) is True
    assert due(now, "06:00", today) is False            # 오늘 이미 돎
    assert due(now, None, None) is False and due(now, "", None) is False and due(now, "아침", None) is False   # 꺼짐
    assert due(datetime(2026, 11, 17, 5, 59), "06:00", None) is False and due(now, "6:00", None) is True
    assert parse_at("25:00") is None and parse_at(" 7:5 ") == "07:05"
