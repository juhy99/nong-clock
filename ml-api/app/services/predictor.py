"""가격 예측기.

지금은 DummyPredictor 가 그럴듯한 가짜 값을 돌려준다. 같은 (품목, 지역, 기준일) 이면
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

from app.core.catalog import ITEMS
from app.core.config import MODEL_VERSION
from app.schemas.prediction import (
    ForecastPoint,
    Horizon,
    PredictResponse,
    PricePoint,
    WeatherAlert,
)

HISTORY_DAYS = 14


class Predictor(Protocol):
    def predict(self, item: str, region: str, horizon: Horizon, base_date: date) -> PredictResponse: ...


def _rng(*parts: object) -> random.Random:
    # hash() 는 프로세스마다 달라지므로 고정 해시로 시드를 만든다.
    key = "|".join(str(p) for p in parts).encode()
    return random.Random(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))


class DummyPredictor:
    def predict(self, item: str, region: str, horizon: Horizon, base_date: date) -> PredictResponse:
        info = ITEMS[item]
        rng = _rng(item, region, base_date)

        # 최근 실제 시세: 기준가 주변의 랜덤워크
        history: list[PricePoint] = []
        price = info.base_price * rng.uniform(0.85, 0.95)
        for i in range(HISTORY_DAYS, 0, -1):
            price *= 1 + rng.gauss(0, 0.015)
            history.append(PricePoint(date=base_date - timedelta(days=i), price=round(price)))
        history.append(PricePoint(date=base_date, price=info.base_price))

        # 예측: 품목·지역별 추세 + 시간이 갈수록 넓어지는 오차범위
        daily_drift = rng.uniform(-0.012, 0.015)
        forecast: list[ForecastPoint] = []
        price = float(info.base_price)
        for t in range(1, horizon + 1):
            price *= 1 + daily_drift + rng.gauss(0, 0.004)
            band = price * 0.03 * math.sqrt(t)
            forecast.append(
                ForecastPoint(
                    date=base_date + timedelta(days=t),
                    price=round(price),
                    lower=round(price - band),
                    upper=round(price + band),
                )
            )

        predicted = forecast[-1].price
        alerts: list[WeatherAlert] = []
        if horizon >= 14:
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
            unit=info.unit,
            region=region,
            horizon=horizon,
            base_date=base_date,
            base_price=info.base_price,
            history=history,
            forecast=forecast,
            predicted_price=predicted,
            change_pct=round((predicted - info.base_price) / info.base_price * 100, 1),
            confidence=max(0, 92 - horizon // 2 - rng.randint(0, 6)),
            alerts=alerts,
            model_version=MODEL_VERSION,
        )


@lru_cache
def get_predictor() -> Predictor:
    return DummyPredictor()
