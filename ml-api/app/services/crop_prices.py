"""작물 추천에 쓰는 가격 (11-13) — 가격 예측 화면과 같은 DB 예측 표를 읽는다.

- 도매가(전국 · 품목 전체): DB price_forecast_daily 의 그 품목(variety_id = ALL), 오늘 이전에 만든 가장 최근 기준일 예측.
  하한·상한도 그 표 값 그대로 (예측 화면의 범위와 같음). off_season = 월 예측(12달)이 끝난 뒤 평년 × 비율로 낸 참고값 (11-16)
  11-16: 예측 표에 일요일·출하철 밖 날이 없음 → 그날 값이 없으면 앞 3일 → 뒤 3일 안 가장 가까운 날 (가격 예측 화면 fcAt 과 같음), 그래도 없으면 평년
- 예측이 없는 날(예측 표 365일 밖 · 표에 없는 품목 · DB 없이 실행): crops.json 의 평년 도매가(2021~2025 같은 달 평균, 범위 = 그 5해 최저·최고)
- 농가가 받는 값 = 도매가 × farm_ratio (작형마다, crops.json) · 쌀·콩(price_source = survey)은 조사 수취가격 그대로 (예측 없음)
- 시장 계수: DB market_factor (품목 × 시장 × 달) — 가격 예측 화면이 시장별 값을 낼 때 쓰는 것과 같음. 없으면 1
DB 를 쓰는 조건은 가격 예측과 같다: 환경 변수 PREDICTOR=db (+ PG* 접속 정보). 결과는 10분 동안 기억 (예측 표는 하루 한 번 바뀜)
"""

import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta

from app.core.config import PREDICTOR
from app.core.crop_catalog import Crop, Cropping

CACHE_SECONDS = 600


@dataclass(frozen=True)
class Price:
    wholesale: float      # 전국 도매가 (원/kg)
    low: float
    high: float
    basis: str            # forecast · normal · survey
    off_season: bool = False


class _Store:
    def __init__(self):
        self._lock = threading.Lock()
        self._fc: dict[str, tuple[float, dict[date, tuple[float, float, float, bool]], date | None]] = {}
        self._fac: dict[str, tuple[float, dict[tuple[str, int], float]]] = {}

    @staticmethod
    def _q(sql: str, params: tuple) -> list[tuple]:
        if PREDICTOR != "db":
            return []
        from app.services.db_predictor import get_db_predictor  # DB 예측기와 같은 연결 (잠금 · 다시 연결 포함)

        try:
            return get_db_predictor()._q(sql, params)
        except Exception:  # DB 가 꺼져 있거나 표가 없으면 평년 가격으로
            return []

    def forecast(self, item: str, today: date, variety: str = "ALL") -> tuple[dict[date, tuple[float, float, float, bool]], date | None]:
        """{목표일: (가격, 하한, 상한, 출하철 밖)}, 기준일. variety = 품종 작형(11-14)이면 그 품종 줄"""
        now = time.monotonic()
        key = item if variety == "ALL" else f"{item}|{variety}"
        with self._lock:
            hit = self._fc.get(key)
            if hit and now - hit[0] < CACHE_SECONDS:
                return hit[1], hit[2]
        rows = []
        for cols in ("base_date, target_date, price, price_low, price_high, off_season", "base_date, target_date, price, price_low, price_high"):
            rows = self._q(
                f"SELECT {cols} FROM price_forecast_daily WHERE item_code = %s AND variety_id = %s AND base_date = "
                "(SELECT max(base_date) FROM price_forecast_daily WHERE item_code = %s AND variety_id = %s AND base_date <= %s) ORDER BY target_date",
                (item, variety, item, variety, today))
            if rows:
                break
        out = {t: (float(p), float(lo if lo is not None else p), float(hi if hi is not None else p), bool(rest[0]) if rest else False)
               for _, t, p, lo, hi, *rest in rows}
        base = rows[0][0] if rows else None
        with self._lock:
            self._fc[key] = (now, out, base)
        return out, base

    def factors(self, item: str) -> dict[tuple[str, int], float]:
        now = time.monotonic()
        with self._lock:
            hit = self._fac.get(item)
            if hit and now - hit[0] < CACHE_SECONDS:
                return hit[1]
        rows = self._q("SELECT market_code, month, factor FROM market_factor WHERE item_code = %s AND factor IS NOT NULL", (item,))
        out = {(m, int(mo)): float(f) for m, mo, f in rows}
        with self._lock:
            self._fac[item] = (now, out)
        return out


STORE = _Store()


def _normal(crop: Crop, d: date, c: Cropping | None = None) -> tuple[float, float, float] | None:
    """평년 도매가 (그 달 값이 비었으면 — 철 밖 달 — 값이 있는 달들의 평균). 품종 작형이면 그 품종 평년"""
    src = c if c is not None and c.price_variety and c.normal_price else crop
    if not src.normal_price:
        return None
    i = d.month - 1
    p = src.normal_price[i]
    if p is None:
        vals = [v for v in src.normal_price if v is not None]
        if not vals:
            return None
        p = sum(vals) / len(vals)
        return p, min(v for v in src.normal_low if v is not None), max(v for v in src.normal_high if v is not None)
    lo = src.normal_low[i] if src.normal_low and src.normal_low[i] is not None else p
    hi = src.normal_high[i] if src.normal_high and src.normal_high[i] is not None else p
    return p, lo, hi


def wholesale(crop: Crop, d: date, today: date, c: Cropping | None = None) -> Price | None:
    """그날 전국 도매가 (예측 → 없으면 평년). 쌀·콩은 None (조사 수취가격을 farm_price 에서 바로 씀).
    c 가 품종 작형(11-14, price_variety)이면 그 품종의 예측·평년"""
    if crop.price_source == "survey":
        return None
    fc, _ = STORE.forecast(crop.code, today, c.price_variety if c is not None and c.price_variety else "ALL")
    hit = next((x for x in [d] + [d - timedelta(days=i) for i in (1, 2, 3)] + [d + timedelta(days=i) for i in (1, 2, 3)] if x in fc), None)
    if hit is not None:
        p, lo, hi, off = fc[hit]
        return Price(p, lo, hi, "forecast", off)
    n = _normal(crop, d, c)
    return Price(n[0], n[1], n[2], "normal") if n else None


def farm_price(crop: Crop, c: Cropping, d: date, today: date) -> Price | None:
    """그날 농가가 받는 값 (원/kg) = 도매가 × 농가 수취 비율"""
    if crop.price_source == "survey":
        p = float(crop.survey_price or c.survey.price)
        return Price(p, p, p, "survey")
    w = wholesale(crop, d, today, c)
    if w is None:
        return None
    k = c.farm_ratio or 1.0
    return Price(w.wholesale * k, w.low * k, w.high * k, w.basis, w.off_season)


# 11-16: 작물 추천은 시·도 안 시장 중 순이익이 가장 큰 곳을 고르므로, 계수 표의 이상값(창원팔용 피망 ×6.1, 마늘 ×3.1 등
#   — 그 시장만 다른 규격·품종이 섞인 것으로 보임)이 늘 뽑혀 순이익이 부풀었다. 추천에서는 0.67~1.5배로 자름 (계수 95% 가 이 안).
#   가격 예측 화면의 시장별 값은 그 시장 실제 시세와 맞춰 보이므로 그대로 둠
FACTOR_MIN, FACTOR_MAX = 0.67, 1.5


def market_factor(crop: Crop, market: str | None, month: int) -> float:
    if not market or market == "national" or crop.price_source == "survey":
        return 1.0
    f = STORE.factors(crop.code).get((market, month), 1.0)
    return min(FACTOR_MAX, max(FACTOR_MIN, f))


def forecast_base(crop: Crop, today: date) -> date | None:
    return STORE.forecast(crop.code, today)[1] if crop.price_source != "survey" else None


__all__ = ["Price", "STORE", "farm_price", "forecast_base", "market_factor", "wholesale"]
