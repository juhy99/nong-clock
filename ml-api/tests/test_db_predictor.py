"""DB 예측기 (11-11) — DB 없이 가짜 행으로 계산 규칙만 확인"""

from datetime import date

import pytest

from app.services.db_predictor import DbPredictor, NoForecast

BASE = date(2026, 11, 11)
BM = date(2026, 9, 1)


class FakeDb(DbPredictor):
    """_q 가 받은 SQL 첫 부분으로 가짜 행을 돌려줌"""

    def __init__(self, monthly, prices=None, factors=None, daily=None):
        super().__init__(connect=lambda: None)
        self.monthly, self.prices, self.factors = monthly, prices or [(date(2026, 11, 3), 1000.0)], factors or []
        self.daily = daily  # None = 일 단위 표가 없는 DB (예전 판)

    def _q(self, sql, params=()):
        if sql.startswith("SELECT unit_id"):
            return [(1, "복숭아(백도)")]
        if sql.startswith("SELECT month, factor"):
            return self.factors
        if "price_forecast_daily" in sql:
            if self.daily is None:
                raise RuntimeError('relation "price_forecast_daily" does not exist')
            item, vid, _, _, _, d0, d1 = params
            return [r[1:] for r in self.daily if r[0] == (item, vid) and d0 < r[2] <= d1]
        if "price_forecast_monthly" in sql:
            return self.monthly
        return self.prices


def row(y, m, p, lo=None, hi=None):
    return (BM, date(y, m, 1), p, lo if lo is not None else p * 0.8, hi if hi is not None else p * 1.2, "v4 시험")


def test_month_value_on_15th_and_line_between():
    P = FakeDb([row(2026, 11, 1000), row(2026, 12, 1300)])
    r = P.predict("onion", "national", 40, BASE, 14)
    d = {f.date: f.price for f in r.forecast}
    assert d[date(2026, 11, 15)] == 1000
    assert d[date(2026, 12, 15)] == 1300
    assert 1000 < d[date(2026, 11, 30)] < 1300  # 15일 사이는 직선
    assert r.base_price == 1000 and r.model_version.startswith("v4 시험 · 기준월 2026-09")


def test_months_without_forecast_are_skipped():
    P = FakeDb([row(2027, 6, 4000), row(2027, 7, 3500)])
    r = P.predict("peach", "national", 300, BASE, 14)
    assert r.forecast[0].date == date(2027, 6, 1) and r.forecast[-1].date == date(2027, 7, 31)
    with pytest.raises(NoForecast):
        P.predict("peach", "national", 30, BASE, 14)  # 6월 전에는 예측 없음


def test_market_factor_by_target_month():
    P = FakeDb([row(2026, 12, 1000)], factors=[(12, 1.1)])
    r = P.predict("onion", "110001", 40, BASE, 14)
    assert {f.date: f.price for f in r.forecast}[date(2026, 12, 15)] == 1100


def test_variety_echo_and_unknown_variety():
    P = FakeDb([row(2027, 6, 4000)])
    assert P.predict("peach", "national", 250, BASE, 14, False, "peach-1").variety == "peach-1"
    with pytest.raises(KeyError):
        P.predict("peach", "national", 250, BASE, 14, False, "peach-99")


# ── 일 단위 표 (11-12) ──
DB_BASE = date(2026, 11, 10)


def drow(item, vid, d, p):
    return ((item, vid), DB_BASE, d, p, p * 0.8, p * 1.3)


def test_daily_table_used_first_and_values_as_is():
    daily = [drow("onion", "ALL", date(2026, 11, 12), 1050), drow("onion", "ALL", date(2026, 11, 13), 1060), drow("onion", "ALL", date(2026, 11, 20), 990)]
    P = FakeDb([row(2026, 11, 5000)], daily=daily)
    r = P.predict("onion", "national", 9, BASE, 14)
    assert [(f.date, f.price) for f in r.forecast] == [(date(2026, 11, 12), 1050), (date(2026, 11, 13), 1060), (date(2026, 11, 20), 990)]
    assert r.forecast[0].lower == 840 and r.forecast[0].upper == 1365
    assert r.model_version == "섞기(u7c·v4·원인) · 기준일 2026-11-10"


def test_daily_table_horizon_and_market_factor():
    daily = [drow("onion", "ALL", date(2026, 11, 12), 1000), drow("onion", "ALL", date(2026, 12, 2), 1000)]
    P = FakeDb([], daily=daily, factors=[(12, 1.1)])
    r = P.predict("onion", "110001", 21, BASE, 14)       # 12-02 는 기준일 + 21일 = 12-02 → 들어감
    assert {f.date: f.price for f in r.forecast} == {date(2026, 11, 12): 1000, date(2026, 12, 2): 1100}
    assert len(P.predict("onion", "110001", 20, BASE, 14).forecast) == 1


def test_variety_daily_and_fallback_to_monthly():
    daily = [drow("peach", "peach-1", date(2027, 6, 20), 4100)]
    P = FakeDb([row(2027, 6, 4000)], daily=daily)
    assert P.predict("peach", "national", 250, BASE, 14, False, "peach-1").forecast[0].price == 4100
    r = P.predict("peach", "national", 250, BASE, 14)    # 품목 전체(ALL)는 일 표에 없음 → 월 표
    assert r.model_version.startswith("v4 시험 · 기준월")


def test_no_daily_table_in_old_db_uses_monthly():
    r = FakeDb([row(2026, 11, 1000)]).predict("onion", "national", 10, BASE, 14)
    assert r.forecast and r.model_version.startswith("v4 시험")


# ── 11-13 보안·트래픽: 같은 질문 10분 기억 · 여러 요청이 동시에 와도 안전 ──
class Counting(FakeDb):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.calls = 0

    def _q(self, sql, params=()):
        self.calls += 1
        return super()._q(sql, params)


def test_same_question_is_answered_from_memory_as_a_copy():
    P = Counting([row(2026, 11, 1000), row(2026, 12, 1300)])
    a = P.predict("onion", "national", 40, BASE, 14)
    n = P.calls
    b = P.predict("onion", "national", 40, BASE, 14)
    assert P.calls == n  # 두 번째는 DB 를 다시 읽지 않음
    assert a == b and a is not b  # 같은 값, 다른 객체 (받은 쪽이 고쳐도 기억은 그대로)
    b.region = "고친 값"
    assert P.predict("onion", "national", 40, BASE, 14).region != "고친 값"
    P.predict("onion", "national", 30, BASE, 14)  # 다른 질문은 새로 계산
    assert P.calls > n


def test_no_forecast_is_remembered_too():
    P = Counting([row(2027, 6, 4000)])
    for _ in range(3):
        with pytest.raises(NoForecast):
            P.predict("peach", "national", 30, BASE, 14)
    first = P.calls
    with pytest.raises(NoForecast):
        P.predict("peach", "national", 30, BASE, 14)
    assert P.calls == first


def test_many_requests_at_once():
    from concurrent.futures import ThreadPoolExecutor

    P = FakeDb([row(2026, 11, 1000), row(2026, 12, 1300)])
    with ThreadPoolExecutor(16) as ex:
        rs = list(ex.map(lambda h: P.predict("onion", "national", 20 + h % 20, BASE, 14), range(200)))
    assert all(r.forecast for r in rs) and len({r.horizon for r in rs}) == 20


# ── 11-13 출하철 밖 표시 (off_season) ──
class OffDb(FakeDb):
    """일 단위 표에 off_season 열이 있는 DB. old=True 면 그 열이 없는 예전 판 (열을 부르면 오류)"""

    def __init__(self, rows, old=False):
        super().__init__([], daily=rows)
        self.old = old

    def _q(self, sql, params=()):
        if "price_forecast_daily" in sql:
            if "off_season" in sql and self.old:
                raise RuntimeError('column "off_season" does not exist')
            item, vid, _, _, _, d0, d1 = params
            return [r[1:] if "off_season" in sql else r[1:6] for r in self.daily if r[0] == (item, vid) and d0 < r[2] <= d1]
        return super()._q(sql, params)


def _off_rows():
    return [(("onion", "ALL"), BASE, date(2026, 11, 12), 1000, 900, 1100, 0), (("onion", "ALL"), BASE, date(2026, 11, 13), 1010, 900, 1100, 1)]


def test_off_season_flag_comes_through():
    r = OffDb(_off_rows()).predict("onion", "national", 2, BASE, 14)
    assert [f.off_season for f in r.forecast] == [False, True]


def test_old_table_without_off_season_column_still_works():
    r = OffDb(_off_rows(), old=True).predict("onion", "national", 2, BASE, 14)
    assert [f.price for f in r.forecast] == [1000, 1010] and not any(f.off_season for f in r.forecast)
