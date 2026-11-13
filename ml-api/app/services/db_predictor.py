"""DB 예측기 (11-11, 일 단위 표 11-12) — PostgreSQL farmdb 의 실제 시세 + 예측 표로 /predict 에 답한다.

켜는 법: 환경 변수 PREDICTOR=db 와 DB 접속 정보(PGHOST · PGPORT · PGDATABASE · PGUSER · PGPASSWORD). 없으면 DummyPredictor 그대로.
- 최근 시세(history)·기준가·작년 같은 시기: 품목은 price_daily(시장·ALL 등급), 품종은 price_unit_daily(전국)의 예측 단위들 금액 합 ÷ 물량 합.
  품종 + 시장이면 전국 품종 시세 × 그 시장 계수(market_factor) — 원장 품종 시세가 전국만 있어서
- 예측(forecast): ① 일 단위 표 price_forecast_daily (python-ml/3_forecast.py, 11-12) — 요청 기준일 이전에 만든 가장 최근 기준일의 하루 값 그대로.
  ② 일 단위 표에 그 품목·품종이 없으면 월 예측 표(price_forecast_monthly): 기준일이 든 달보다 앞선 가장 최근 기준월, 달 15일에 값을 두고 이웃 달 사이 직선.
  예측이 없는 날(출하철 밖)은 빼고, 고른 기간에 예측이 하나도 없으면 NoForecast → 404
- 시장: 전국 예측 × market_factor(품목·시장·목표 달). 그 달 계수가 없으면 1
- 오차 범위: 표의 하한·상한 그대로, error_pct = 고른 날의 (상한 − 하한) ÷ 2 ÷ 예측 × 100
- (11-13 보안·트래픽) 같은 질문의 답은 10분 동안 기억해 두고 다시 씀 (예측 표는 하루 한 번 바뀜) → 사람이 몰려도 DB 를 덜 읽음.
  DB 연결 하나를 여러 요청(스레드)이 같이 쓰므로 한 번에 한 질문만 보내게 잠금
"""

import os
import threading
import time
from datetime import date, timedelta
from functools import lru_cache

from app.core.catalog import ITEMS, NATIONAL
from app.core.markets import market_name
from app.core.shared import load
from app.schemas.prediction import ForecastPoint, Horizon, PredictResponse, PricePoint

HISTORY_DAYS = 14
LAST_YEAR_DAYS = 364
BASE_LOOKBACK_DAYS = 30  # 기준일에 거래가 없으면 이만큼 앞까지 가장 최근 시세를 기준가로
CACHE_SECONDS = 600       # 같은 예측 질문을 기억하는 시간 (10분)
CACHE_MAX = 5000          # 기억하는 답의 최대 개수 (넘으면 비우고 다시)


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
        self._lock = threading.Lock()
        self._cache: dict[tuple, tuple[float, object]] = {}

    @staticmethod
    def _pg():
        import psycopg2  # 필요할 때만 (더미 모드·테스트에서는 없어도 됨)

        return psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "5432"), dbname=os.getenv("PGDATABASE", "farmdb"),
            user=os.getenv("PGUSER", "postgres"), password=os.getenv("PGPASSWORD", ""),
        )

    def _q(self, sql: str, params: tuple = ()) -> list[tuple]:
        with self._lock:
            return self._q_locked(sql, params)

    def _q_locked(self, sql: str, params: tuple) -> list[tuple]:
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
    def _daily_table(self, item: str, variety: str, base_date: date, horizon: int, fac: dict[int, float]):
        """일 단위 표에서 (요청 기준일 이전에 만든 가장 최근 기준일, 예측 점들). 표가 없거나 줄이 없으면 (None, [])"""
        where = ("FROM price_forecast_daily WHERE item_code = %s AND variety_id = %s AND base_date = (SELECT max(base_date) FROM price_forecast_daily "
                 "WHERE item_code = %s AND variety_id = %s AND base_date <= %s) AND target_date > %s AND target_date <= %s ORDER BY target_date")
        args = (item, variety or "ALL", item, variety or "ALL", base_date, base_date, base_date + timedelta(days=horizon))
        rows = None
        # 출하철 밖 표시(off_season, 11-13) 열이 있는 표부터. 없는 예전 판이면 그 열 없이, 표 자체가 없으면 월 표로
        for cols in ("base_date, target_date, price, price_low, price_high, off_season", "base_date, target_date, price, price_low, price_high"):
            try:
                rows = self._q(f"SELECT {cols} " + where, args)
                break
            except Exception:
                continue
        if rows is None:
            return None, []
        pts = []
        for _, t, p, lo, hi, *rest in rows:
            f = fac.get(t.month, 1.0)
            pts.append(ForecastPoint(date=t, price=round(p * f), lower=round((lo if lo is not None else p) * f), upper=round((hi if hi is not None else p) * f),
                                     off_season=bool(rest[0]) if rest else False))
        return (rows[0][0] if rows else None), pts

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
        """같은 질문은 10분 동안 기억한 답(예측 없음 NoForecast 도)을 돌려줌. 받은 쪽이 고쳐도 기억은 그대로이게 복사본으로"""
        key = (item, market, horizon, base_date, history_days, last_year, variety)
        now = time.monotonic()
        hit = self._cache.get(key)
        if hit is None or now - hit[0] >= CACHE_SECONDS:
            try:
                value = self._predict(item, market, horizon, base_date, history_days, last_year, variety)
            except NoForecast as e:
                value = e
            if len(self._cache) >= CACHE_MAX:
                self._cache.clear()
            hit = self._cache[key] = (now, value)
        if isinstance(hit[1], NoForecast):
            raise NoForecast(str(hit[1]))
        return hit[1].model_copy()

    def _predict(self, item: str, market: str, horizon: Horizon, base_date: date, history_days: int,
                 last_year: bool, variety: str) -> PredictResponse:
        info = ITEMS[item]
        fac = self._factors(item, market)
        hist_all = self._prices(item, market, variety, base_date - timedelta(days=history_days + BASE_LOOKBACK_DAYS), base_date, fac)
        if not hist_all:
            raise NoForecast("기준일 앞 30일 동안 이 품목·시장의 거래가 없어요")
        base_price = hist_all[-1].price
        history = [h for h in hist_all if h.date >= base_date - timedelta(days=history_days)] or hist_all[-1:]
        fb, forecast = self._daily_table(item, variety, base_date, horizon, fac)
        if forecast:
            version = f"섞기(u7c·v4·원인) · 기준일 {fb:%Y-%m-%d}"
        else:
            monthly = self._monthly(item, variety, base_date)
            forecast = self._daily(monthly, base_date, horizon, fac)
            version = f"{monthly[0][5]} · 기준월 {monthly[0][0]:%Y-%m}" if monthly else ""
        if not forecast:
            raise NoForecast("고른 기간에는 예측이 없어요 (출하철이 아니거나 아직 예측을 만들지 않은 기간)")
        last = forecast[-1]
        err = round((last.upper - last.lower) / 2 / last.price * 100, 1) if last.price else 0.0
        ly = []
        if last_year:
            ly = self._prices(item, market, variety, base_date - timedelta(days=history_days + LAST_YEAR_DAYS),
                              base_date + timedelta(days=horizon - LAST_YEAR_DAYS), fac)
        return PredictResponse(
            item=item, item_name=info.name, code4=info.code4, unit=info.unit, market=market, market_name=market_name(market),
            region=NATIONAL, horizon=horizon, base_date=base_date, base_price=base_price, history=history, forecast=forecast,
            predicted_price=last.price, change_pct=round((last.price - base_price) / base_price * 100, 1) if base_price else 0.0,
            error_pct=err, reference=None, confidence=max(0, min(100, round(100 - err))), alerts=[], last_year=ly,
            model_version=version, variety=variety,
        )


@lru_cache
def get_db_predictor() -> DbPredictor:
    return DbPredictor()
