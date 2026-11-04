"""가격 예측기.

지금은 DummyPredictor 가 그럴듯한 가짜 값을 돌려준다 (최대 365일, 도매시장별). 같은 (품목, 시장, 기준일) 이면
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

from app.core.catalog import ITEMS, LONG_RANGE_DAYS, NATIONAL
from app.core.config import MODEL_VERSION
from app.core.markets import market_factor, market_name
from app.schemas.prediction import (
    ForecastPoint,
    Horizon,
    PredictResponse,
    PricePoint,
    WeatherAlert,
)

HISTORY_DAYS = 14


class Predictor(Protocol):
    def predict(self, item: str, market: str, horizon: Horizon, base_date: date) -> PredictResponse: ...


def _rng(*parts: object) -> random.Random:
    # hash() 는 프로세스마다 달라지므로 고정 해시로 시드를 만든다.
    key = "|".join(str(p) for p in parts).encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))


def _season(item: str, d: date) -> float:
    """품목마다 고정된 1년 주기 계절 모양: 1 ± 진폭(8~30%), 가장 비싼 때는 품목마다 다름"""
    r = _rng("season", item)
    amp, peak = r.uniform(0.08, 0.30), r.randint(0, 364)
    return 1 + amp * math.cos(2 * math.pi * (d.timetuple().tm_yday - peak) / 365)


def band_ratio(t: int) -> float:
    """오차 범위 비율: 2.5% × √일수, 90일 넘으면 더 빨리 커짐 (최대 ±40%)"""
    long = 1 + (t - LONG_RANGE_DAYS) / 365 if t > LONG_RANGE_DAYS else 1
    return min(0.4, 0.025 * math.sqrt(t) * long)


class DummyPredictor:
    """전국 도매시장 평균의 가짜 예측 × 시장 계수 (markets.market_factor). 시장별 모델이 붙으면 이 클래스를 바꾼다."""

    def predict(self, item: str, market: str, horizon: Horizon, base_date: date) -> PredictResponse:
        info = ITEMS[item]
        f = market_factor(item, market)
        base = round(info.base_price * f)
        rng = _rng(item, market, base_date)

        # 최근 실제 시세: 기준가 주변의 랜덤워크
        history: list[PricePoint] = []
        price = base * rng.uniform(0.88, 0.96)
        for i in range(HISTORY_DAYS, 0, -1):
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
            band = v * band_ratio(t)
            forecast.append(ForecastPoint(date=d, price=round(v), lower=round(v - band), upper=round(v + band)))

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
            confidence=max(5, 92 - int(math.sqrt(horizon) * 4) - rng.randint(0, 6)),
            alerts=alerts,
            model_version=MODEL_VERSION,
        )


@lru_cache
def get_predictor() -> Predictor:
    return DummyPredictor()
