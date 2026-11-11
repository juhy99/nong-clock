"""DB 예측기 (11-11) — PostgreSQL farmdb 의 실제 시세 + 월 예측 표(price_forecast_monthly)로 /predict 에 답한다.

켜는 법: 환경 변수 PREDICTOR=db 와 DB 접속 정보(PGHOST · PGPORT · PGDATABASE · PGUSER · PGPASSWORD). 없으면 DummyPredictor 그대로.
- 최근 시세(history)·기준가·작년 같은 시기: 품목은 price_daily(시장·ALL 등급), 품종은 price_unit_daily(전국)의 예측 단위들 금액 합 ÷ 물량 합.
  품종 + 시장이면 전국 품종 시세 × 그 시장 계수(market_factor) — 원장 품종 시세가 전국만 있어서
- 예측(forecast): 기준일이 든 달보다 앞선 가장 최근 기준월의 월 예측. 달 가운데(15일)에 값을 두고 이웃 달 사이는 직선으로 잇는다.
  예측이 없는 달(출하철 밖)의 날은 빼고, 고른 기간에 예측이 하나도 없으면 NoForecast → 404
- 시장: 전국 예측 × market_factor(품목·시장·목표 달). 그 달 계수가 없으면 1
- 오차 범위: 표의 하한·상한 그대로, error_pct = 고른 날의 (상한 − 하한) ÷ 2 ÷ 예측 × 100
"""

import os
from datetime import date, timedelta
from functools import lru_cache

from app.core.catalog import ITEMS, NATIONAL
from app.core.markets import market_name
from app.core.shared import load
from app.schemas.prediction import ForecastPoint, Horizon, PredictResponse, PricePoint

HISTORY_DAYS = 14
LAST_YEAR_DAYS = 364
BASE_LOOKBACK_DAYS = 30  # 기준일에 거래가 없으면 이만큼 앞까지 가장 최근 시세를 기준가로


class NoForecast(Exception):
    """고른 품목·품종·기간에 예측이 없음 (출하철 밖 등)"""


def _varieties() -> dict[tuple[str, str], list[str]]:
    """(품목 코드, 품종 id) → 예측 단위 이름들 (shared/items50.json)"""
    out = {}
    for it in load("items50.json")["items"]:
        for v in it.get("varieties", []):
            out[(it["code"], v["id"])] = v["units"]
    return out


class DbPredictor:
    def __init__(self, connect=None):
        self._connect = connect or self._pg
        self._con = None
        self._vars = _varieties()
        self._unit_ids: dict[str, int] | None = None

    @staticmethod
    def _pg():
        import psycopg2  # 필요할 때만 (더미 모드·테스트에서는 없어도 됨)

        return psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "5432"), dbname=os.getenv("PGDATABASE", "farmdb"),
            user=os.getenv("PGUSER", "postgres"), password=os.getenv("PGPASSWORD", ""),
        )

    def _q(self, sql: str, params: tuple = ()) -> list[tuple]:
        for attempt in (0, 1):  # 연결이 끊겼으면 한 번 다시 연결
            try:
                if self._con is None:
                    self._con = self._connect()
                cur = self._con.cursor()
                cur.execute(sql, params)
                rows = cur.fetchall()
                cur.close()
                self._con.rollback()  # 읽기만 — 트랜잭션을 열어 두지 않음
                return rows
            except Exception:
                self._con = None
                if attempt:
                    raise
        return []

    # ── 시세 ──
    def _units(self, item: str, variety: str) -> list[int]:
        if self._unit_ids is None:
            self._unit_ids = {name: uid for uid, name in self._q("SELECT unit_id, unit_name FROM variety_unit")}
        names = self._vars.get((item, variety))
        if names is None:
            raise KeyError(variety)
        return [self._unit_ids[n] for n in names if n in self._unit_ids]

    def _factors(self, item: str, market: str) -> dict[int, float]:
        if market == NATIONAL:
            return {}
        return {m: float(f) for m, f in self._q("SELECT month, factor FROM market_factor WHERE item_code = %s AND market_code = %s AND factor IS NOT NULL", (item, market))}

    def _prices(self, item: str, market: str, variety: str, d0: date, d1: date, fac: dict[int, float]) -> list[PricePoint]:
        if variety:
            rows = self._q(
                "SELECT date, sum(amount_won) / NULLIF(sum(volume_kg), 0) FROM price_unit_daily WHERE unit_id = ANY(%s) AND date BETWEEN %s AND %s GROUP BY date ORDER BY date",
                (self._units(item, variety), d0, d1),
            )
            k = (lambda d: fac.get(d.month, 1.0)) if market != NATIONAL else (lambda d: 1.0)
        else:
            rows = self._q(
                "SELECT date, price FROM price_daily WHERE item_code = %s AND market_code = %s AND grade = 'ALL' AND date BETWEEN %s AND %s ORDER BY date",
                (item, market, d0, d1),
            )
            k = lambda d: 1.0
        return [PricePoint(date=d, price=round(float(p) * k(d))) for d, p in rows if p is not None]

    # ── 예측 ──
    def _monthly(self, item: str, variety: str, base_date: date):
        first = base_date.replace(day=1)
        rows = self._q(
            "SELECT base_month, target_month, price, price_low, price_high, model FROM price_forecast_monthly "
            "WHERE item_code = %s AND variety_id = %s AND base_month = (SELECT max(base_month) FROM price_forecast_monthly WHERE item_code = %s AND base_month < %s) "
            "ORDER BY target_month",
            (item, variety or "ALL", item, first),
        )
        return rows

    @staticmethod
    def _daily(monthly, base_date: date, horizon: int, fac: dict[int, float]) -> list[ForecastPoint]:
        """월 값을 그 달 15일에 두고 이웃 달(바로 다음 달)끼리 직선으로 잇는다. 예측 없는 달은 비움"""
        pts = {(t.year, t.month): (date(t.year, t.month, 15), p, lo, hi) for _, t, p, lo, hi, _ in monthly}

        def at(d: date):
            key = (d.year, d.month)
            if key not in pts:
                return None
            a = pts[key]
            nb = (d.year + (d.month == 12), d.month % 12 + 1) if d >= a[0] else (d.year - (d.month == 1), (d.month - 2) % 12 + 1)
            b = pts.get(nb)
            if b is None:
                return a[1:]
            w = (d - a[0]).days / (b[0] - a[0]).days
            return tuple(x + (y - x) * w if x is not None and y is not None else x for x, y in zip(a[1:], b[1:]))

        out = []
        for t in range(1, horizon + 1):
            d = base_date + timedelta(days=t)
            v = at(d)
            if v is None:
                continue
            f = fac.get(d.month, 1.0)
            p, lo, hi = v[0] * f, (v[1] if v[1] is not None else v[0]) * f, (v[2] if v[2] is not None else v[0]) * f
            out.append(ForecastPoint(date=d, price=round(p), lower=round(lo), upper=round(hi)))
        return out

    def predict(self, item: str, market: str, horizon: Horizon, base_date: date, history_days: int = HISTORY_DAYS,
                last_year: bool = False, variety: str = "") -> PredictResponse:
        info = ITEMS[item]
        fac = self._factors(item, market)
        hist_all = self._prices(item, market, variety, base_date - timedelta(days=history_days + BASE_LOOKBACK_DAYS), base_date, fac)
        if not hist_all:
            raise NoForecast("기준일 앞 30일 동안 이 품목·시장의 거래가 없어요")
        base_price = hist_all[-1].price
        history = [h for h in hist_all if h.date >= base_date - timedelta(days=history_days)] or hist_all[-1:]
        monthly = self._monthly(item, variety, base_date)
        forecast = self._daily(monthly, base_date, horizon, fac)
        if not forecast:
            raise NoForecast("고른 기간에는 예측이 없어요 (출하철이 아니거나 아직 예측을 만들지 않은 기간)")
        last = forecast[-1]
        err = round((last.upper - last.lower) / 2 / last.price * 100, 1) if last.price else 0.0
        ly = []
        if last_year:
            ly = self._prices(item, market, variety, base_date - timedelta(days=history_days + LAST_YEAR_DAYS),
                              base_date + timedelta(days=horizon - LAST_YEAR_DAYS), fac)
        bm = monthly[0][0]
        return PredictResponse(
            item=item, item_name=info.name, code4=info.code4, unit=info.unit, market=market, market_name=market_name(market),
            region=NATIONAL, horizon=horizon, base_date=base_date, base_price=base_price, history=history, forecast=forecast,
            predicted_price=last.price, change_pct=round((last.price - base_price) / base_price * 100, 1) if base_price else 0.0,
            error_pct=err, reference=None, confidence=max(0, min(100, round(100 - err))), alerts=[], last_year=ly,
            model_version=f"{monthly[0][5]} · 기준월 {bm:%Y-%m}", variety=variety,
        )


@lru_cache
def get_db_predictor() -> DbPredictor:
    return DbPredictor()
