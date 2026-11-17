"""DB 예측기 (11-11, 일 단위 표 11-12) — PostgreSQL farmdb 의 실제 시세 + 예측 표로 /predict 에 답한다.

켜는 법: 환경 변수 PREDICTOR=db 와 DB 접속 정보(PGHOST · PGPORT · PGDATABASE · PGUSER · PGPASSWORD). 없으면 DummyPredictor 그대로.
- 최근 시세(history)·기준가·작년 같은 시기: 품목은 price_daily(시장·ALL 등급), 품종은 price_unit_daily(전국)의 예측 단위들 금액 합 ÷ 물량 합.
  품종 + 시장이면 전국 품종 시세 × 그 시장 계수(market_factor) — 원장 품종 시세가 전국만 있어서
- 예측(forecast): ① 일 단위 표 price_forecast_daily (python-ml/3_forecast.py, 11-12) — 요청 기준일 이전에 만든 가장 최근 기준일의 하루 값 그대로.
  ② 일 단위 표에 그 품목·품종이 아예 없으면(예전 DB) 월 예측 표(price_forecast_monthly): 기준일이 든 달보다 앞선 가장 최근 기준월, 달 15일에 값을 두고 이웃 달 사이 직선.
  예측이 없는 날(출하철 밖)은 빼고, 고른 기간에 예측이 하나도 없으면 NoForecast → 404
- 시장: 전국 예측 × market_factor(품목·시장·목표 달). 그 달 계수가 없으면 1
- 오차 범위: 표의 하한·상한 그대로 (시험 기간 실제÷예측의 10%~90%)
- error_pct·confidence (11-17): 최종 모델 시험 정확도 (app/core/final_accuracy.py, 품종 → 품목 → 전체). 전에는 범위 폭의 절반이라
  품목과 상관없이 같은 값이고 가까운 날일수록 크게 나왔음
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
from app.core import final_accuracy
from app.core.shared import load
from app.schemas.prediction import ForecastPoint, Horizon, PredictResponse, PricePoint

HISTORY_DAYS = 14
LAST_YEAR_DAYS = 364
BASE_LOOKBACK_DAYS = 30  # 기준일에 거래가 없으면 이만큼 앞까지 가장 최근 시세를 기준가로
OLD_LOOKBACK_DAYS = 400  # 11-16: 30일 안에 거래가 없으면(철이 끝난 품종) 1년 남짓 앞까지 찾아 마지막 거래를 기준가로 (base_stale)
BASE_AVG_DAYS = 7        # 11-14: 기준가 = 마지막 거래일까지 7일(달력) 금액 합 ÷ 물량 합 (하루 얇은 거래 하나에 흔들리지 않게)
STALE_DAYS = 7           # 11-14: 마지막 거래가 기준일보다 이만큼 넘게 앞이면 '지금 가격'이 오래됨 → base_stale (급등락 카드에서 뺌)
CACHE_SECONDS = 600       # 같은 예측 질문을 기억하는 시간 (10분)
CACHE_MAX = 5000          # 기억하는 답의 최대 개수 (넘으면 비우고 다시)


class NoForecast(Exception):
    """고른 품목·품종·기간에 예측이 없음 (출하철 밖 등). season = 출하철 안내 (11-16, _season) — 화면이 '다음 철 예측 보기' 버튼을 만듦"""

    def __init__(self, message: str, season: dict | None = None):
        super().__init__(message)
        self.season = season


SEASON_YEARS = 3      # 출하철 안내의 거래량 비중: 기준일 앞 다 찬 3개 해
THIN_SHARE = 0.01     # 11-17: 지난 3개 해 그 달 거래량이 1년의 1% 밑이면 '거래가 거의 없는 달' → 표에 값이 있어도 예측을 보이지 않음
                      #        (예: 자두 후무사 11월 18,459원/kg — 마지막 거래 11/2 4,000원). 가격은 쓰지 않고 거래량만 씀
SEASON_GAP_DAYS = 10  # 예측 표에서 이보다 오래 비면 철이 끝난 것으로 봄 (일요일·공휴일은 이어짐)


def month_label(months: list[int]) -> str:
    """[7, 8, 9, 10] → "7~10월", [11, 12, 1, 2] → "11~2월", [3, 4, 9, 10] → "3~4월 · 9~10월" (달이 이어진 묶음)"""
    ms = sorted(set(months))
    if not ms:
        return ""
    if len(ms) == 12:
        return "1년 내내"
    runs, cur = [], [ms[0]]
    for m in ms[1:]:
        if m == cur[-1] + 1:
            cur.append(m)
        else:
            runs.append(cur); cur = [m]
    runs.append(cur)
    if len(runs) > 1 and runs[0][0] == 1 and runs[-1][-1] == 12:   # 12월 → 1월로 넘어가는 철은 한 묶음
        runs[0] = runs.pop() + runs[0]
    return " · ".join(f"{r[0]}월" if len(r) == 1 else f"{r[0]}~{r[-1]}월" for r in runs)


def _labels() -> dict[tuple[str, str], str]:
    """(품목 코드, 품종 id) → 품종 이름 (화면 안내 문구용)"""
    return {(it["code"], v["id"]): v["label"] for it in load("items50.json")["items"] for v in it.get("varieties", [])}


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
        self._labels = _labels()
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

    def _base_avg(self, item: str, market: str, variety: str, last: date, fac: dict[int, float]) -> float | None:
        """마지막 거래일까지 BASE_AVG_DAYS 일 금액 합 ÷ 물량 합. 금액·물량이 없으면 None (→ 마지막 날 값)"""
        d0 = last - timedelta(days=BASE_AVG_DAYS - 1)
        try:
            if variety:
                rows = self._q("SELECT sum(amount_won) / NULLIF(sum(volume_kg), 0) AS base_avg FROM price_unit_daily WHERE unit_id = ANY(%s) AND date BETWEEN %s AND %s",
                               (self._units(item, variety), d0, last))
                k = fac.get(last.month, 1.0) if market != NATIONAL else 1.0
            else:
                rows = self._q("SELECT sum(amount_won) / NULLIF(sum(volume_kg), 0) AS base_avg FROM price_daily WHERE item_code = %s AND market_code = %s AND grade = 'ALL' AND date BETWEEN %s AND %s",
                               (item, market, d0, last))
                k = 1.0
        except Exception:
            return None
        v = rows[0][0] if rows and rows[0] else None
        return float(v) * k if isinstance(v, (int, float)) or hasattr(v, "as_integer_ratio") else None

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
        # 폭락 보정(crash_adj, 11-14)·출하철 밖(off_season, 11-13) 열이 있는 표부터. 없는 예전 판이면 그 열 없이, 표 자체가 없으면 월 표로
        for cols in ("base_date, target_date, price, price_low, price_high, off_season, crash_adj",
                     "base_date, target_date, price, price_low, price_high, off_season", "base_date, target_date, price, price_low, price_high"):
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
                                     off_season=bool(rest[0]) if rest else False, crash_adj=bool(rest[1]) if len(rest) > 1 else False))
        return (rows[0][0] if rows else None), pts

    def _in_daily_table(self, item: str, variety: str, base_date: date) -> bool:
        """11-17: 이 품목·품종이 일 단위 표(기준일 이전에 만든 판)에 한 번이라도 있나. 표가 없는 예전 DB 면 False (→ 월 표)"""
        try:
            return bool(self._q("SELECT 1 AS has_daily FROM price_forecast_daily WHERE item_code = %s AND variety_id = %s AND base_date <= %s LIMIT 1",
                                (item, variety or "ALL", base_date)))
        except Exception:
            return False

    def _season(self, item: str, variety: str, base_date: date, horizon: int) -> dict | None:
        """11-16: 고른 기간에 예측이 없을 때 안내 — 주로 거래되는 달(예측 표에 값이 있는 달), 그 달들의 지난 3년 거래량 비중,
        다음 철 첫날·끝날 (기준일 + 365일 안). 예: "황도 거래는 주로 7~10월이에요 (1년 거래량의 97%)" """
        try:
            rows = self._q(
                "SELECT target_date FROM price_forecast_daily WHERE item_code = %s AND variety_id = %s AND base_date = (SELECT max(base_date) "
                "FROM price_forecast_daily WHERE item_code = %s AND variety_id = %s AND base_date <= %s) AND target_date > %s AND off_season = 0 "
                "ORDER BY target_date", (item, variety or "ALL", item, variety or "ALL", base_date, base_date))
            days = [r[0] for r in rows]
            months = sorted({d.month for d in days})
            share = None
            if months:
                units = self._units(item, variety) if variety else sorted({u for (it, v) in self._vars if it == item for u in self._units(item, v)})
                y0 = date(base_date.year - SEASON_YEARS, 1, 1)
                vol = {int(m): float(v or 0) for m, v in self._q(
                    "SELECT extract(month FROM date)::int AS season_m, sum(volume_kg) FROM price_unit_daily "
                    "WHERE unit_id = ANY(%s) AND date >= %s AND date < %s GROUP BY 1", (units, y0, date(base_date.year, 1, 1)))}
                total = sum(vol.values())
                if total:   # 안내의 '주로 ○월'에는 거래량이 1년의 1% 넘는 달만 (예측은 있어도 몇 상자뿐인 달은 빼서 읽기 쉽게)
                    months = [m for m in months if vol.get(m, 0.0) / total >= 0.01] or months
                share = round(sum(vol.get(m, 0.0) for m in months) / total * 100) if total else None
        except Exception:
            return None
        name = ITEMS[item].name + (f" {self._labels.get((item, variety), '')}" if variety else "")
        end_pick = base_date + timedelta(days=horizon)
        nxt = [d for d in days if d > end_pick and d.month in months]   # 다음 철 = 안내한 달 (몇 상자뿐인 달은 건너뜀)
        start = nxt[0] if nxt else None
        end = None
        if start:
            end = start
            for d in nxt[1:]:
                if (d - end).days > SEASON_GAP_DAYS:
                    break
                end = d
        label = month_label(months)
        md = lambda d: f"{d.month}/{d.day}"
        main = share is None or share >= 80   # 그 달들에 거래가 몰렸을 때만 '주로' (양파 중만생처럼 저장해 1년 내내 팔면 비중이 낮음)
        if not label:
            head = ""
        elif main:
            head = f"{name} 거래는 주로 {label}이에요" + (f" (1년 거래량의 {share}%)" if share is not None else "") + ". "
        else:
            head = f"{name} 예측은 {label}에만 있어요 (팀 모델의 출하철, 그 달 거래량 = 1년의 {share}%). "
        tail = f"{md(base_date + timedelta(days=1))}~{md(end_pick)}은 " + ("거래가 거의 없는 철이라 예측하지 않아요" if main else "출하철 밖이라 예측하지 않아요")
        if not start:
            tail += " (앞으로 1년 안에는 예측이 없어요)"
        return {"months": months, "label": label, "share": share, "next_start": start.isoformat() if start else None,
                "next_end": end.isoformat() if end else None, "message": head + tail}

    def _thin_months(self, item: str, variety: str, base_date: date) -> set[int]:
        """11-17: 지난 3개 해 거래량이 1년의 THIN_SHARE 밑인 달 (거래량 자료가 없으면 빈 집합 = 거르지 않음)"""
        try:
            units = self._units(item, variety) if variety else sorted({u for (it, v) in self._vars if it == item for u in self._units(item, v)})
            y0 = date(base_date.year - SEASON_YEARS, 1, 1)
            vol = {int(m): float(v or 0) for m, v in self._q(
                "SELECT extract(month FROM date)::int AS thin_m, sum(volume_kg) FROM price_unit_daily "
                "WHERE unit_id = ANY(%s) AND date >= %s AND date < %s GROUP BY 1", (units, y0, date(base_date.year, 1, 1)))}
        except Exception:
            return set()
        total = sum(vol.values())
        if not total:
            return set()
        return {m for m in range(1, 13) if vol.get(m, 0.0) / total < THIN_SHARE}

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
            raise NoForecast(str(hit[1]), hit[1].season)
        return hit[1].model_copy()

    def _predict(self, item: str, market: str, horizon: Horizon, base_date: date, history_days: int,
                 last_year: bool, variety: str) -> PredictResponse:
        info = ITEMS[item]
        fac = self._factors(item, market)
        hist_all = self._prices(item, market, variety, base_date - timedelta(days=history_days + BASE_LOOKBACK_DAYS), base_date, fac)
        if not hist_all:   # 11-16: 철이 끝나 최근 30일 거래가 없으면 1년 남짓 앞의 마지막 거래 (화면에 🕒 '오래된 지금 가격'), 그것도 없으면 안내
            hist_all = self._prices(item, market, variety, base_date - timedelta(days=OLD_LOOKBACK_DAYS), base_date, fac)[-8:]
        if not hist_all:
            season = self._season(item, variety, base_date, horizon)
            # 11-17: 이 시장에만 거래가 없는 경우 — 철 안내의 "○/○~○/○은 거래가 거의 없는 철" · 다음 철 날짜는 전국 기준이라 맞지 않음 → 이 시장 사정으로 바꿈
            where = market_name(market) if market != NATIONAL else "전국 도매시장"
            msg = (season["message"].split(". ")[0] + ". " if season and season["label"] else "") + f"{where}에서는 최근 1년 동안 이 품목 거래가 없어 예측하지 않아요. 다른 지역을 골라 보세요"
            if season:
                season = {**season, "message": msg, "next_start": None, "next_end": None, "no_market_trade": True}
            raise NoForecast(msg, season)
        last_trade = hist_all[-1].date
        avg = self._base_avg(item, market, variety, last_trade, fac)
        base_price = round(avg) if avg else hist_all[-1].price
        stale = (base_date - last_trade).days > STALE_DAYS
        # 11-17: 작년 같은 7일과 견줘 얼마나 올랐나/내렸나 (예측값에는 안 씀, 화면 안내용). 오래된 가격이면 안 냄
        ly_avg = None if stale else self._base_avg(item, market, variety, last_trade - timedelta(days=LAST_YEAR_DAYS), fac)
        trend = round(avg / ly_avg, 2) if avg and ly_avg else None
        history = [h for h in hist_all if h.date >= base_date - timedelta(days=history_days)] or hist_all[-1:]
        fb, forecast = self._daily_table(item, variety, base_date, horizon, fac)
        if forecast:
            thin = self._thin_months(item, variety, base_date)
            forecast = [f for f in forecast if f.date.month not in thin]   # 11-17: 거래가 거의 없는 달은 빼서 출하철 밖처럼 (아래에서 다 비면 안내)
        if forecast:
            version = f"섞기(u7c·v4·원인) · 기준일 {fb:%Y-%m-%d}"
        elif self._in_daily_table(item, variety, base_date):
            version = ""   # 11-17: 일 단위 표에 있는데 고른 기간만 빔 = 출하철 밖 → 아래에서 안내 (옛 월 표로 채우지 않음)
        else:
            monthly = self._monthly(item, variety, base_date)
            forecast = self._daily(monthly, base_date, horizon, fac)
            version = f"{monthly[0][5]} · 기준월 {monthly[0][0]:%Y-%m}" if monthly else ""
        if not forecast:
            season = self._season(item, variety, base_date, horizon)
            raise NoForecast(season["message"] if season else "고른 기간에는 예측이 없어요 (출하철이 아니거나 아직 예측을 만들지 않은 기간)", season)
        last = forecast[-1]
        acc, _ = final_accuracy.accuracy(item, variety, (last.date - base_date).days)
        err = round(100 - acc, 1)
        ly = []
        if last_year:
            ly = self._prices(item, market, variety, base_date - timedelta(days=history_days + LAST_YEAR_DAYS),
                              base_date + timedelta(days=horizon - LAST_YEAR_DAYS), fac)
        return PredictResponse(
            item=item, item_name=info.name, code4=info.code4, unit=info.unit, market=market, market_name=market_name(market),
            region=NATIONAL, horizon=horizon, base_date=base_date, base_price=base_price, base_price_date=last_trade, base_stale=stale,
            trend_vs_last_year=trend,
            history=history, forecast=forecast,
            predicted_price=last.price, change_pct=round((last.price - base_price) / base_price * 100, 1) if base_price else 0.0,
            error_pct=err, reference=None, confidence=max(0, min(100, round(100 - err))), alerts=[], last_year=ly,
            model_version=version, variety=variety,
        )


@lru_cache
def get_db_predictor() -> DbPredictor:
    return DbPredictor()
