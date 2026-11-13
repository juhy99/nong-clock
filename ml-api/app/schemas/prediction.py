from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.catalog import MAX_HISTORY_DAYS, MAX_HORIZON, NATIONAL

# 오늘로부터 며칠 뒤까지 예측할지. 1 ~ MAX_HORIZON(365)일 중 아무 값이나 가능
Horizon = Annotated[int, Field(ge=1, le=MAX_HORIZON)]


class PredictRequest(BaseModel):
    item: str = Field(examples=["napa_cabbage"], description="품목 코드 (GET /items 참고)")
    market: str = Field(NATIONAL, examples=["110001"], description="도매시장 코드 (GET /markets). 생략하거나 national 이면 전국 도매시장 평균")
    region: str = Field(NATIONAL, examples=[NATIONAL], description="(예전 방식) 지역 코드. 지금은 national 만 — market 을 쓰세요")
    horizon: Horizon = Field(examples=[28], description="예측 기간(일). 1~365 중 아무 값. forecast 에 기준일 다음 날부터 그날까지 일별 경로가 온다")
    base_date: date | None = Field(None, examples=["2026-11-10"], description="기준일 (11-11). 생략하면 오늘. 오늘부터 1년 전까지. 기준일 시세가 base_price, 그 뒤 horizon 일을 예측")
    history_days: int = Field(14, ge=1, le=MAX_HISTORY_DAYS, description="기준일 앞 실제 시세를 며칠 치 줄지 (11-11, 기본 14). 화면은 8주 = 56")
    last_year: bool = Field(False, description="true 면 작년 같은 시기 실제 시세(last_year)도 줌 (11-11)")
    variety: str = Field("", examples=["peach-1"], description="품종 id (shared/items50.json, 11-11). 비우면 품목 전체. DB 예측기만 씀 — 더미는 무시하고 variety 를 빈 값으로 돌려줌")


class PricePoint(BaseModel):
    date: date
    price: int


class ForecastPoint(PricePoint):
    lower: int = Field(description="예측 오차범위 하단")
    upper: int = Field(description="예측 오차범위 상단")
    off_season: bool = Field(False, description="출하철 밖 날 — 두 모델 다 채점해 본 적 없는 달이라 참고용 (11-13, DB 예측 표 off_season)")


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
    last_year: list[PricePoint] = Field(default_factory=list, description="작년 같은 시기 실제 시세 (요청 last_year=true 일 때). 52주(364일) 전 같은 요일로, history 첫날 ~ forecast 마지막 날과 같은 기간. date 는 작년 날짜")
    model_version: str
    variety: str = Field("", description="이 응답의 품종 id. 빈 값 = 품목 전체 (더미 예측기는 늘 빈 값 → 화면이 가짜 품종 계수를 곱함)")


class TopMover(BaseModel):
    item: str
    item_name: str
    unit: str
    predicted_price: int
    change_pct: float
    confidence: int = Field(ge=0, le=100)
    error_pct: float = 0
    reference: Literal["far", "baseline"] | None = None
