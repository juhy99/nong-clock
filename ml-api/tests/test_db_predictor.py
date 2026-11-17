"""DB 예측기 (11-11) — DB 없이 가짜 행으로 계산 규칙만 확인"""

from datetime import date, timedelta

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

    month_vol = []    # 11-17: [(달, 거래량kg)]
    base_avg = None   # 11-14 기준가 7일 금액÷물량 (None = 금액·물량 없음)

    def _q(self, sql, params=()):
        if "AS base_avg" in sql:
            return [(self.base_avg,)]
        if sql.startswith("SELECT unit_id"):
            return [(1, "복숭아(백도)")]
        if sql.startswith("SELECT month, factor"):
            return self.factors
        if "AS thin_m" in sql:   # 11-17: 달별 거래량 (없으면 빈 목록 = 거르지 않음)
            return self.month_vol
        if "AS has_daily" in sql:   # 11-17: 그 품목·품종이 일 단위 표에 한 번이라도 있나
            if self.daily is None:
                raise RuntimeError('relation "price_forecast_daily" does not exist')
            return [(1,)] if any(r[0] == (params[0], params[1]) for r in self.daily) else []
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


def test_variety_in_daily_table_but_off_season_does_not_use_old_monthly():
    """11-17: 일 단위 표에 그 품종이 있는데 고른 기간만 비면(출하철 밖) 빈칸·안내 — 예전엔 월 표(11-09 옛 v4, 기준월 2026-09)를
    직선으로 이어 보여 줘서 양파 저장(onion-3) 등 21개 품종이 옛 예측·일요일 값으로 나왔음"""
    daily = [drow("peach", "peach-1", date(2027, 6, 20), 4100)]
    P = FakeDb([row(2026, 11, 3000), row(2026, 12, 3100)], daily=daily)
    with pytest.raises(NoForecast):
        P.predict("peach", "national", 30, BASE, 14, False, "peach-1")


def test_forecast_hidden_in_months_with_almost_no_trade():
    """11-17: 표에 값이 있어도 지난 3년 그 달 거래량이 1년의 1% 밑이면 보이지 않음 (거래량만 씀, 가격은 안 씀)
    예: 자두 후무사 11월 18,459원/kg (마지막 거래 11/2 4,000원)"""
    daily = [drow("plum", "plum-5", date(2026, 11, 20), 18000), drow("plum", "plum-5", date(2026, 12, 5), 19000)]
    P = FakeDb([], daily=daily)
    P.month_vol = [(6, 400_000.0), (7, 500_000.0), (8, 90_000.0), (11, 2_000.0), (12, 1_000.0)]   # 11·12월 = 0.2%·0.1%
    with pytest.raises(NoForecast):
        P.predict("plum", "national", 30, DB_BASE, 14, False, "plum-5")
    P2 = FakeDb([], daily=daily)
    P2.month_vol = [(11, 300_000.0), (12, 200_000.0), (6, 500_000.0)]   # 11·12월이 충분하면 그대로
    assert len(P2.predict("plum", "national", 30, DB_BASE, 14, False, "plum-5").forecast) == 2


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


# ── 11-14 폭락 보정 표시 (crash_adj) ──
class CrashDb(OffDb):
    """crash_adj 열까지 있는 DB. no_crash=True 면 그 열만 없는 11-13 판"""

    def __init__(self, rows, no_crash=False):
        super().__init__(rows)
        self.no_crash = no_crash

    def _q(self, sql, params=()):
        if "price_forecast_daily" in sql and "crash_adj" in sql:
            if self.no_crash:
                raise RuntimeError('column "crash_adj" does not exist')
            item, vid, _, _, _, d0, d1 = params
            return [r[1:] for r in self.daily if r[0] == (item, vid) and d0 < r[2] <= d1]
        if "price_forecast_daily" in sql and "off_season" in sql:
            item, vid, _, _, _, d0, d1 = params
            return [r[1:7] for r in self.daily if r[0] == (item, vid) and d0 < r[2] <= d1]
        return super()._q(sql, params)


def _crash_rows():
    return [(("onion", "ALL"), BASE, date(2026, 11, 12), 700, 600, 900, 0, 1), (("onion", "ALL"), BASE, date(2026, 11, 13), 710, 600, 900, 1, 0)]


def test_crash_flag_comes_through():
    r = CrashDb(_crash_rows()).predict("onion", "national", 2, BASE, 14)
    assert [f.crash_adj for f in r.forecast] == [True, False] and [f.off_season for f in r.forecast] == [False, True]


def test_table_without_crash_column_still_works():
    r = CrashDb(_crash_rows(), no_crash=True).predict("onion", "national", 2, BASE, 14)
    assert [f.price for f in r.forecast] == [700, 710] and [f.off_season for f in r.forecast] == [False, True] and not any(f.crash_adj for f in r.forecast)


def test_old_table_without_off_season_column_still_works():
    r = OffDb(_off_rows(), old=True).predict("onion", "national", 2, BASE, 14)
    assert [f.price for f in r.forecast] == [1000, 1010] and not any(f.off_season for f in r.forecast)


# ── 11-14 기준가 7일 금액÷물량 · 오래된 기준가 ──
def test_base_price_is_7day_volume_weighted():
    P = FakeDb([row(2026, 11, 1000)], prices=[(date(2026, 11, 9), 1200.0), (date(2026, 11, 10), 200.0)])
    P.base_avg = 1150.4
    r = P.predict("onion", "national", 30, BASE, 14)
    assert r.base_price == 1150 and r.base_price_date == date(2026, 11, 10) and not r.base_stale


def test_base_price_falls_back_to_last_day_and_marks_stale():
    P = FakeDb([row(2026, 11, 1000)], prices=[(date(2026, 11, 2), 900.0)])
    r = P.predict("onion", "national", 30, BASE, 14)
    assert r.base_price == 900 and r.base_stale   # 11-02 → 11-11 은 9일


# ── 11-16 출하철 밖 안내 (예측 없음 + 언제 주로 거래되는지 + 다음 철) ──
from app.services.db_predictor import month_label


def test_month_label():
    assert month_label([7, 8, 9, 10]) == "7~10월"
    assert month_label([11, 12, 1, 2]) == "11~2월"
    assert month_label([3, 4, 9]) == "3~4월 · 9월"
    assert month_label(list(range(1, 13))) == "1년 내내"


class SeasonDb(FakeDb):
    """황도처럼 7~10월에만 예측이 있는 품종. 지난 3년 달별 물량도 줌"""

    def _q(self, sql, params=()):
        if "season_m" in sql:
            return [(6, 500.0), (7, 3700.0), (8, 7000.0), (9, 4800.0), (10, 350.0), (11, 0.1)]
        if "price_forecast_daily" in sql and "off_season = 0" in sql:
            d0 = date(2027, 7, 1)
            return [(d0 + timedelta(days=i),) for i in range(0, 123) if (d0 + timedelta(days=i)).weekday() != 6]
        if "price_forecast_daily" in sql:
            return []
        if "price_forecast_monthly" in sql:
            return []
        return super()._q(sql, params)


def test_off_season_tells_when_and_next_season():
    P = SeasonDb([])
    with pytest.raises(NoForecast) as e:
        P.predict("peach", "national", 180, BASE, 14, False, "peach-1")
    s = e.value.season
    assert s["label"] == "7~10월" and s["share"] == 97 and s["next_start"] == "2027-07-01" and s["next_end"] == "2027-10-30"   # 10-31 은 일요일(휴장)
    assert "주로 7~10월" in str(e.value) and "1년 거래량의 97%" in str(e.value)
    with pytest.raises(NoForecast) as e2:   # 기억한 답(캐시)에서도 안내가 그대로
        P.predict("peach", "national", 180, BASE, 14, False, "peach-1")
    assert e2.value.season == s


def test_no_recent_trade_uses_last_trade_within_a_year():
    """철이 끝나 최근 30일 거래가 없는 품종: 1년 안의 마지막 거래를 '지금 가격'으로 (오래됨 표시), 예측이 있으면 보여 줌"""
    P = FakeDb([], prices=[(date(2026, 9, 5), 1500.0)], daily=[drow("onion", "ALL", date(2026, 11, 20), 1200)])
    calls = []
    orig = P._q
    def q(sql, params=()):
        if sql.startswith("SELECT date, price FROM price_daily"):
            calls.append(params[3])
            return [(date(2026, 9, 5), 1500.0)] if params[2] <= date(2026, 9, 5) else []
        return orig(sql, params)
    P._q = q
    r = P.predict("onion", "national", 30, DB_BASE, 14)
    assert r.base_price == 1500 and r.base_stale and r.base_price_date == date(2026, 9, 5) and r.forecast

# ── 11-17 작년 같은 7일 대비 (화면 ⚠️ 안내용, 예측값엔 안 씀) ──
class TrendDb(FakeDb):
    def _q(self, sql, params=()):
        if "AS base_avg" in sql:
            return [(3000.0 if params[-1] > date(2026, 1, 1) else 1000.0,)]   # 올해 3,000 · 작년 1,000
        return super()._q(sql, params)


def test_trend_vs_last_year():
    P = TrendDb([row(2026, 11, 1000)], prices=[(date(2026, 11, 10), 3000.0)])
    r = P.predict("onion", "national", 30, BASE, 14)
    assert r.trend_vs_last_year == 3.0 and r.base_price == 3000


def test_no_trend_when_base_is_stale_or_no_amount():
    P = TrendDb([row(2026, 11, 1000)], prices=[(date(2026, 11, 2), 900.0)])
    assert P.predict("onion", "national", 30, BASE, 14).trend_vs_last_year is None   # 오래된 가격
    Q = FakeDb([row(2026, 11, 1000)], prices=[(date(2026, 11, 10), 900.0)])
    assert Q.predict("onion", "national", 30, BASE, 14).trend_vs_last_year is None   # 금액·물량 없음
