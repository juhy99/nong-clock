"""DB 예측기 (11-11) — DB 없이 가짜 행으로 계산 규칙만 확인"""

from datetime import date

import pytest

from app.services.db_predictor import DbPredictor, NoForecast

BASE = date(2026, 11, 11)
BM = date(2026, 9, 1)


class FakeDb(DbPredictor):
    """_q 가 받은 SQL 첫 부분으로 가짜 행을 돌려줌"""

    def __init__(self, monthly, prices=None, factors=None):
        super().__init__(connect=lambda: None)
        self.monthly, self.prices, self.factors = monthly, prices or [(date(2026, 11, 3), 1000.0)], factors or []

    def _q(self, sql, params=()):
        if sql.startswith("SELECT unit_id"):
            return [(1, "복숭아(백도)")]
        if sql.startswith("SELECT month, factor"):
            return self.factors
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
