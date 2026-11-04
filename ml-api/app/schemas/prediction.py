from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.catalog import MAX_HORIZON, NATIONAL

# 오늘로부터 며칠 뒤까지 예측할지. 1 ~ MAX_HORIZON(365)일 중 아무 값이나 가능
Horizon = Annotated[int, Field(ge=1, le=MAX_HORIZON)]


class PredictRequest(BaseModel):
    item: str = Field(examples=["napa_cabbage"], description="품목 코드 (GET /items 참고)")
    market: str = Field(NATIONAL, examples=["110001"], description="도매시장 코드 (GET /markets). 생략하거나 national 이면 전국 도매시장 평균")
    region: str = Field(NATIONAL, examples=[NATIONAL], description="(예전 방식) 지역 코드. 지금은 national 만 — market 을 쓰세요")
    horizon: Horizon = Field(examples=[90], description="예측 기간(일). 1~365 중 아무 값 (화면에서 고른 날짜 - 기준일). forecast 에 오늘 다음 날부터 그날까지 일별 경로가 온다")


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
    code4: str = Field("", description="공영도매 품목코드")
    unit: str
    market: str = Field(NATIONAL, description="도매시장 코드")
    market_name: str = Field("전국 평균")
    region: str
    horizon: Horizon
    base_date: date
    base_price: int = Field(description="기준일 공영도매시장 경매 단가(원/kg)")
    history: list[PricePoint] = Field(description="최근 실제 시세")
    forecast: list[ForecastPoint] = Field(description="기준일 다음 날부터 horizon 일까지 일별 예측. lower·upper = 예측 ± 모델 검증 오차(WAPE)")
    predicted_price: int = Field(description="horizon 일 후 예상 도매가(원/kg)")
    change_pct: float = Field(description="기준가 대비 변동률(%)")
    error_pct: float = Field(0, description="고른 날(horizon)의 예측 오차 ±% = 모델 검증 오차(WAPE, 품목·기간별). 6개월보다 먼 날은 6개월 값보다 넓게")
    reference: Literal["far", "baseline"] | None = Field(None, description="참고용: far 6개월보다 먼 날 · baseline 이 품목·기간은 기준선(오늘 가격 그대로)보다 나쁨")
    confidence: int = Field(ge=0, le=100, description="신뢰도 지수 = 100 − 예측 오차(%)")
    alerts: list[WeatherAlert]
    model_version: str


class TopMover(BaseModel):
    item: str
    item_name: str
    unit: str
    predicted_price: int
    change_pct: float
    confidence: int = Field(ge=0, le=100)
    error_pct: float = 0
    reference: Literal["far", "baseline"] | None = None
