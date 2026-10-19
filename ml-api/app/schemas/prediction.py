from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.core.catalog import NATIONAL

Horizon = Literal[7, 14, 30]


class PredictRequest(BaseModel):
    item: str = Field(examples=["napa_cabbage"], description="품목 코드 (GET /items 참고)")
    region: str = Field(NATIONAL, examples=[NATIONAL], description="지역 코드 (GET /regions 참고). 생략하면 전국")
    horizon: Horizon = Field(examples=[14], description="예측 시점(일)")


class PricePoint(BaseModel):
    date: date
    price: int


class ForecastPoint(PricePoint):
    lower: int = Field(description="예측 오차범위 하단")
    upper: int = Field(description="예측 오차범위 상단")


class WeatherAlert(BaseModel):
    """'예측이 깨지는 구간' — 이상기후로 모델 신뢰도가 떨어지는 기간."""

    start: date
    end: date
    reason: str
    mape_normal: float = Field(description="평상시 백테스트 MAPE(%)")
    mape_anomaly: float = Field(description="유사 이상기후 구간 백테스트 MAPE(%)")


class PredictResponse(BaseModel):
    item: str
    item_name: str
    unit: str
    region: str
    horizon: Horizon
    base_date: date
    base_price: int = Field(description="기준일 도매가(원/kg)")
    history: list[PricePoint] = Field(description="최근 실제 시세")
    forecast: list[ForecastPoint] = Field(description="기준일 다음 날부터 horizon 일까지 예측")
    predicted_price: int = Field(description="horizon 일 후 예상 도매가(원/kg)")
    change_pct: float = Field(description="기준가 대비 변동률(%)")
    confidence: int = Field(ge=0, le=100, description="신뢰도 지수")
    alerts: list[WeatherAlert]
    model_version: str


class TopMover(BaseModel):
    item: str
    item_name: str
    unit: str
    predicted_price: int
    change_pct: float
    confidence: int = Field(ge=0, le=100)
