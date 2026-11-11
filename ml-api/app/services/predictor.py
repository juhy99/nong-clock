"""가격 예측기.

지금은 DummyPredictor 가 그럴듯한 가짜 값을 돌려준다 (최대 365일, 도매시장별). 가격 선은 가짜지만
오차 범위(띠)·신뢰도·참고용 표시는 실제 모델 검증 오차(shared/model_accuracy.json)를 따른다. 같은 (품목, 시장, 기준일) 이면
항상 같은 값이 나오므로 프론트·Spring 개발 중 화면이 새로고침마다 바뀌지 않는다.

실제 모델이 준비되면 Predictor 프로토콜을 구현하는 클래스를 만들고
get_predictor() 가 그것을 반환하도록 바꾸면 라우터 코드는 그대로 둘 수 있다.
"""

import hashlib
import math
import random
from datetime import date, timedelta
from functools import lru_cache
from typing import Protocol

from app.core import accuracy
from app.core.catalog import ITEMS, NATIONAL
from app.core.config import MODEL_VERSION
from app.core.markets import market_factor, market_name
from app.schemas.prediction import (
    ForecastPoint,
    Horizon,
    PredictResponse,
    PricePoint,
    WeatherAlert,
)

HISTORY_DAYS = 14  # 기본값 (요청 history_days 로 바꿀 수 있음)
LAST_YEAR_DAYS = 364  # 작년 같은 시기 = 52주 전 같은 요일


class Predictor(Protocol):
    def predict(self, item: str, market: str, horizon: Horizon, base_date: date, history_days: int = HISTORY_DAYS, last_year: bool = False) -> PredictResponse: ...


def _rng(*parts: object) -> random.Random:
    # hash() 는 프로세스마다 달라지므로 고정 해시로 시드를 만든다.
    key = "|".join(str(p) for p in parts).encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))


def _season(item: str, d: date) -> float:
    """품목마다 고정된 1년 주기 계절 모양: 1 ± 진폭(8~30%), 가장 비싼 때는 품목마다 다름"""
    r = _rng("season", item)
    amp, peak = r.uniform(0.08, 0.30), r.randint(0, 364)
    return 1 + amp * math.cos(2 * math.pi * (d.timetuple().tm_yday - peak) / 365)


def band_ratio(item: str, t: int) -> float:
    """오차 범위 비율 = 모델 검증 오차(WAPE) — 품목·예측 기간별 (app/core/accuracy.py)"""
    return accuracy.error_pct(item, t) / 100


class DummyPredictor:
    """전국 도매시장 평균의 가짜 예측 × 시장 계수 (markets.market_factor). 시장별 모델이 붙으면 이 클래스를 바꾼다."""

    def predict(self, item: str, market: str, horizon: Horizon, base_date: date, history_days: int = HISTORY_DAYS, last_year: bool = False) -> PredictResponse:
        info = ITEMS[item]
        f = market_factor(item, market)
        base = round(info.base_price * f)
        rng = _rng(item, market, base_date)

        # 최근 실제 시세: 기준가 주변의 랜덤워크
        history: list[PricePoint] = []
        price = base * rng.uniform(0.88, 0.96)
        for i in range(history_days, 0, -1):
            price *= 1 + rng.gauss(0, 0.015)
            history.append(PricePoint(date=base_date - timedelta(days=i), price=round(price)))
        history.append(PricePoint(date=base_date, price=base))

        # 예측: 계절 모양 + 천천히 흔들리는 잡음, 시간이 갈수록 넓어지는 오차범위
        s0 = _season(item, base_date)
        wob = 0.0
        forecast: list[ForecastPoint] = []
        for t in range(1, horizon + 1):
            d = base_date + timedelta(days=t)
            wob = wob * 0.9 + rng.gauss(0, 0.006)
            v = base * _season(item, d) / s0 * (1 + wob)
            band = v * band_ratio(item, t)
            forecast.append(ForecastPoint(date=d, price=round(v), lower=round(v - band), upper=round(v + band)))

        # 작년 같은 시기 (실제 시세 자리): 계절 모양 × 작년 수준(품목마다 ±12%) + 잡음. 실제 모델·DB 가 붙으면 DB 시세로
        ly: list[PricePoint] = []
        if last_year:
            ly_rng = _rng("last_year", item, market, base_date)
            level = 1 + _rng("ly_level", item, base_date.year).uniform(-0.12, 0.12)
            n = 0.0
            for t in range(-history_days, horizon + 1):
                d = base_date + timedelta(days=t) - timedelta(days=LAST_YEAR_DAYS)
                n = n * 0.85 + ly_rng.gauss(0, 0.01)
                ly.append(PricePoint(date=d, price=round(base * level * _season(item, d) / s0 * (1 + n))))

        predicted = forecast[-1].price
        alerts: list[WeatherAlert] = []
        if horizon >= 9:
            alerts.append(
                WeatherAlert(
                    start=base_date + timedelta(days=7),
                    end=base_date + timedelta(days=9),
                    reason="[더미] 기온 편차 +2.4σ, 강수량 평년 대비 180% 예상",
                    mape_normal=6.2,
                    mape_anomaly=19.8,
                )
            )

        return PredictResponse(
            item=item,
            item_name=info.name,
            code4=info.code4,
            unit=info.unit,
            market=market,
            market_name=market_name(market),
            region=NATIONAL,
            horizon=horizon,
            base_date=base_date,
            base_price=base,
            history=history,
            forecast=forecast,
            predicted_price=predicted,
            change_pct=round((predicted - base) / base * 100, 1),
            error_pct=round(accuracy.error_pct(item, horizon), 1),
            reference=accuracy.reference_of(item, horizon),
            confidence=accuracy.confidence(item, horizon),
            alerts=alerts,
            last_year=ly,
            model_version=MODEL_VERSION,
        )


@lru_cache
def get_predictor() -> Predictor:
    return DummyPredictor()
