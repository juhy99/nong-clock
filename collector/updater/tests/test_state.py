import os
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jobs  # noqa: E402
import state  # noqa: E402

PDF = b"%PDF-1.7\n..."


def touch(p: Path, body=b"x", mtime=None):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    if mtime:
        os.utime(p, (mtime, mtime))
    return p


def fake(tmp_path, ledger=("20261113", "20261114"), v4="01_322_월예측_기준202610_앞으로12달.csv", seed=True):
    d = tmp_path / "data"
    (d / "model" / "forecast_20261110").mkdir(parents=True); (d / "model" / "forecast_20261114").mkdir()
    (d / "model" / "run_20261115").mkdir()   # forecast_ 가 아닌 폴더는 안 봄
    if v4:
        touch(d / "model" / "v4" / "01_322_월예측_기준202609_앞으로12달.csv", mtime=1_000_000)
        touch(d / "model" / "v4" / v4, mtime=2_000_000)
    for x in ledger:
        touch(d / "raw" / "auction" / f"{x}.csv.gz")
    s = tmp_path / "seed"
    if seed:
        touch(s / state.SEED_FILE)
    return d, s


def test_status_reads_latest_dates(tmp_path):
    d, s = fake(tmp_path)
    st = state.status(d, s, date(2026, 11, 17))
    assert st["forecast_base"] == "2026-11-14" and st["v4_base"] == "2026-10" and st["ledger_last"] == "2026-11-14" and st["data_ok"] is True
    assert st["monthly"]["ready"] is False and "이미 2026-10" in st["monthly"]["reason"] and "12월 3일" in st["monthly"]["reason"]


def test_monthly_waits_until_day3(tmp_path):
    d, s = fake(tmp_path, ledger=("20261202",))
    m = state.status(d, s, date(2026, 12, 3))["monthly"]
    assert m["ready"] is False and "12월 3일" in m["reason"]
    touch(d / "raw" / "auction" / "20261203.csv.gz")
    m = state.status(d, s, date(2026, 12, 4))["monthly"]
    assert m["ready"] is True and m["next_base"] == "2026-11" and "2026-11" in m["reason"]


def test_monthly_january_uses_december(tmp_path):
    d, s = fake(tmp_path, ledger=("20270105",), v4="01_322_월예측_기준202611_앞으로12달.csv")
    m = state.status(d, s, date(2027, 1, 6))["monthly"]
    assert m["ready"] is True and m["next_base"] == "2026-12"


def test_monthly_off_without_seed(tmp_path):
    d, s = fake(tmp_path, ledger=("20261205",), seed=False)
    m = state.status(d, s, date(2026, 12, 6))["monthly"]
    assert m["ready"] is False and "seed" in m["reason"]


def test_missing_data_folder(tmp_path):
    st = state.status(tmp_path / "없음", tmp_path / "없음2", date(2026, 11, 17))
    assert st["data_ok"] is False and st["forecast_base"] is None and st["v4_base"] is None and st["sources"] == []
    assert st["monthly"]["ready"] is False and st["wolbo"]["have"] == {"VC": False, "VS": False, "VPO": False, "F": False}


def test_sources_last_row_per_source(tmp_path):
    d, s = fake(tmp_path)
    touch(d / "log" / "collect_log.csv", ("source,started_at,finished_at,ok,rows_in,rows_saved,rows_rejected,api_calls,error,note\n"
          "auction,2026-11-14T06:00:00,2026-11-14T06:01:00,False,0,0,0,1," + "긴 오류 " * 100 + ",\n"
          "auction,2026-11-15T06:00:00,2026-11-15T06:01:00,True,10,10,0,1,,\n"
          "kamis,2026-11-15T06:02:00,2026-11-15T06:03:00,False,0,0,0,1," + "x" * 500 + ",\n").encode("utf-8"))
    src = {x["source"]: x for x in state.status(d, s, date(2026, 11, 17))["sources"]}
    assert src["auction"]["ok"] is True and src["auction"]["error"] is None and src["auction"]["finished_at"] == "2026-11-15T06:01:00"
    assert src["kamis"]["ok"] is False and len(src["kamis"]["error"]) == 200


def test_wolbo_accepts_valid_and_rejects_bad(tmp_path):
    d = tmp_path / "data"
    assert state.save_wolbo(d, "VC202611.pdf", PDF) == "VC202611.pdf"
    assert (d / "manual" / "월보" / "VC202611.pdf").read_bytes() == PDF
    assert state.save_wolbo(d, "vpo202611_감자.PDF", PDF) == "vpo202611_감자.PDF"
    for name, body in (("abc.pdf", PDF), ("VC202611.txt", PDF), ("VC202611.pdf", b"hello"), ("VC202611.pdf", b""),
                       ("VC2026.pdf", PDF), ("", PDF), ("VC202611.pdf", b"%PDF-" + b"0" * state.WOLBO_MAX)):
        with pytest.raises(ValueError) as e:
            state.save_wolbo(d, name, body)
        assert any("가" <= ch <= "힣" for ch in str(e.value))   # 한국어 문장
    assert state.save_wolbo(d, "../../VC202612.pdf", PDF) == "VC202612.pdf"
    assert state.save_wolbo(d, "C:\\Users\\M\\F202611.pdf", PDF) == "F202611.pdf"
    assert all(p.parent == d / "manual" / "월보" for p in tmp_path.rglob("*.[pP][dD][fF]")) and len(list((d / "manual" / "월보").iterdir())) == 4
    assert not list(tmp_path.rglob("*.part"))


def test_wolbo_status_for_month(tmp_path):
    d = tmp_path / "data"
    state.save_wolbo(d, "VC202611.pdf", PDF); state.save_wolbo(d, "F202611.pdf", PDF); state.save_wolbo(d, "VS202610.pdf", PDF)
    w = state.status(d, tmp_path / "seed", date(2026, 11, 20))["wolbo"]
    assert w["month"] == "2026-11" and w["have"] == {"VC": True, "VS": False, "VPO": False, "F": True}


def test_install_v4_backs_up_once(tmp_path):
    d, work = tmp_path / "data", tmp_path / "data" / "v4_작업"
    name = "01_322_월예측_기준202611_앞으로12달.csv"
    res = work / "결과" / "NongClock_자동_기준202611"
    touch(res / "결과_기준202611" / name, b"new1")
    touch(work / "결과" / "_최신.txt", ("D:\\nong-clock-data\\05_DB적재\\data\\v4_작업\\결과\\NongClock_자동_기준202611").encode("utf-8"))   # 윈도우 경로여도 찾음
    touch(d / "model" / "v4" / name, b"team")
    assert "넣음" in jobs.install_v4(work, d)
    bak = d / "model" / "v4" / "01_322_월예측_기준202611_앞으로12달_직접만들기전.csv.bak"
    assert (d / "model" / "v4" / name).read_bytes() == b"new1" and bak.read_bytes() == b"team"
    touch(res / "결과_기준202611" / name, b"new2")
    jobs.install_v4(work, d)
    assert (d / "model" / "v4" / name).read_bytes() == b"new2" and bak.read_bytes() == b"team"   # 백업은 처음 것 그대로
    assert len(list((d / "model" / "v4").glob("*.bak"))) == 1


def test_install_v4_missing_result_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        jobs.install_v4(tmp_path / "v4_작업", tmp_path)


def test_steps_order_and_env(tmp_path):
    app, d = tmp_path / "app", tmp_path / "root" / "05_DB적재" / "data"
    st = jobs.steps(app, d)
    assert [s.name for s in st["daily"]] == ["자료 받기 · 경매 정산가격", "자료 받기 · KAMIS 도·소매", "자료 받기 · 기상특보", "자료 받기 · 산지공판장",
                                             "DB 표 만들기", "DB 에 넣기", "예측 만들기"]
    assert [s.argv[-2:] for s in st["daily"][:4]] == [["collect.py", n] for n in ("auction", "kamis", "warning", "sanji")]   # 날씨·예보 등은 안 받음
    assert [s.must_succeed for s in st["daily"]] == [False] * 4 + [True] * 3
    assert st["daily"][4].env["FARMBID_OUT"] == str(d / "tables_daily") and "FARMBID_OUT" not in st["daily"][6].env
    assert st["daily"][6].env["NC_DATA_ROOT"] == str(tmp_path / "root") and st["daily"][5].argv[-2:] == ["load_db.py", "--init"]
    m = st["monthly"]
    assert [s.name for s in m][:3] == ["추가 자료 받기", "월 예측(v4) 만들기", "월 예측 넣기"] and m[0].must_succeed is False
    assert m[2].call is not None and [s.name for s in m][3:] == [s.name for s in st["daily"]]
    assert m[1].argv[-4:] == ["--raw", str(d / "raw" / "auction"), "--data", str(d / "v4_작업")]


def test_sources_show_only_what_refresh_collects(tmp_path):
    d, s = fake(tmp_path)
    rows = [("fx", "False", "인증키 ECOS_API_KEY 가 없습니다"), ("policy", "False", "정책 수집기 종료코드 1"), ("fcst", "False", "x"),
            ("sanji", "True", ""), ("auction", "True", ""), ("db_load", "True", "")]
    touch(d / "log" / "collect_log.csv", ("source,started_at,finished_at,ok,rows_in,rows_saved,rows_rejected,api_calls,error,note\n"
          + "".join(f"{a},2026-11-17T15:00:00,2026-11-17T15:01:00,{b},0,0,0,0,{c},\n" for a, b, c in rows)).encode("utf-8"))
    assert [x["source"] for x in state.status(d, s, date(2026, 11, 17))["sources"]] == ["auction", "sanji", "db_load"]   # 받는 순서대로, 안 받는 자료는 없음


def _auction_state(d, days):
    touch(d / "raw" / "auction" / "_state.json", __import__("json").dumps(
        {k: ({f"m{i}": ("ok" if i < n else "no_data") for i in range(32)}) for k, n in days.items()}).encode("utf-8"))


def _alerts(d, s, now, history, sources_ok=True):
    st = state.status(d, s, now.date())
    if not sources_ok:
        st["sources"] = [{"source": "auction", "ok": False, "finished_at": None, "error": "HTTP 500"}]
    return state.alerts(d, st, history, now)


def test_alerts_quiet_when_all_good(tmp_path):
    d, s = fake(tmp_path, ledger=("20261116",)); (d / "model" / "forecast_20261116").mkdir()
    _auction_state(d, {"20261115": 0, "20261116": 28})
    ok = [{"job": "daily", "status": "ok", "started_at": "2026-11-17T06:00:00", "finished_at": "2026-11-17T06:16:00"}]
    assert _alerts(d, s, datetime(2026, 11, 17, 9, 0), ok) == []
    assert state.last_trading_day(date(2026, 11, 16)) == date(2026, 11, 14)   # 월요일 아침에는 토요일 자료를 봄 (일요일 쉼)


def test_alerts_failed_or_interrupted_run(tmp_path):
    d, s = fake(tmp_path, ledger=("20261116",)); (d / "model" / "forecast_20261116").mkdir()
    _auction_state(d, {"20261116": 30})
    a = _alerts(d, s, datetime(2026, 11, 17, 9, 0), [{"job": "daily", "status": "failed", "failed_step": "DB 에 넣기", "started_at": "2026-11-17T06:00:00"}])
    assert len(a) == 1 and a[0]["level"] == "bad" and "DB 에 넣기" in a[0]["text"] and "11/17 06:00" in a[0]["text"] and "지금 갱신" in a[0]["text"]
    a = _alerts(d, s, datetime(2026, 11, 17, 9, 0), [{"job": "daily", "status": "interrupted", "started_at": "2026-11-17T06:00:00"}])
    assert a[0]["level"] == "bad" and "끊겼어요" in a[0]["text"]


def test_alerts_yesterday_auction_missing_or_thin_after_morning_run(tmp_path):
    d, s = fake(tmp_path, ledger=("20261116",)); (d / "model" / "forecast_20261116").mkdir()
    ok = [{"job": "daily", "status": "ok", "started_at": "2026-11-18T06:00:00", "finished_at": "2026-11-18T06:16:00"}]
    _auction_state(d, {"20261116": 30, "20261117": 0})
    a = _alerts(d, s, datetime(2026, 11, 18, 7, 0), ok)
    assert len(a) == 1 and a[0]["level"] == "warn" and "11/17 경매 자료가 아직 안 올라왔어요" in a[0]["text"]
    _auction_state(d, {"20261116": 30, "20261117": 9})
    assert "덜 올라왔어요 (시장 9/32곳)" in _alerts(d, s, datetime(2026, 11, 18, 7, 0), ok)[0]["text"]
    _auction_state(d, {"20261116": 30, "20261117": 28})
    assert _alerts(d, s, datetime(2026, 11, 18, 7, 0), ok) == []
    yesterday_run = [{"job": "daily", "status": "ok", "started_at": "2026-11-17T16:08:00", "finished_at": "2026-11-17T16:23:00"}]
    _auction_state(d, {"20261116": 30})
    assert _alerts(d, s, datetime(2026, 11, 18, 5, 0), yesterday_run) == []   # 오늘 아직 안 돌렸으면 조용 (곧 자동 실행이 받음)


def test_alerts_source_failed_stale_forecast_and_running(tmp_path):
    d, s = fake(tmp_path, ledger=("20261116",))   # 예측 폴더는 11-14 까지
    _auction_state(d, {"20261116": 30})
    ok = [{"job": "daily", "status": "ok", "started_at": "2026-11-17T06:00:00", "finished_at": "2026-11-17T06:16:00"}]
    a = _alerts(d, s, datetime(2026, 11, 17, 9, 0), ok, sources_ok=False)
    assert a[0]["level"] == "warn" and "경매 정산가격" in a[0]["text"]
    assert any("예측 기준일이 11/14 에 멈춰" in x["text"] for x in _alerts(d, s, datetime(2026, 11, 20, 9, 0), []))
    assert _alerts(d, s, datetime(2026, 11, 20, 9, 0), [{"job": "daily", "status": "running", "started_at": "2026-11-20T08:59:00"}]) == []
    assert state.alerts(tmp_path / "없음", state.status(tmp_path / "없음", s, date(2026, 11, 17)), [], datetime(2026, 11, 17, 9, 0)) == []
