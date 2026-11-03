from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

LandType = Literal["open", "house", "paddy", "orchard"]


class CropOut(BaseModel):
    code: str
    name: str
    emoji: str
    land_type: LandType
    land_type_name: str
    perennial: bool = Field(description="여러 해 기르는 작물 (심는 날 비교를 하지 않음)")


class Land(BaseModel):
    type: LandType = Field(examples=["house"], description="open 노지 · house 시설 · paddy 논 · orchard 과수원")
    area_pyeong: float = Field(gt=0, le=1_000_000, examples=[600], description="평수")


class RecommendCropsRequest(BaseModel):
    lands: list[Land] = Field(min_length=1, description="보유 토지 (종류마다 하나)")
    start_date: date = Field(description="농사 시작 날짜. 오늘 ~ 30일 뒤")


class Option(BaseModel):
    crop: str
    crop_name: str
    emoji: str
    land_type: LandType
    area_pyeong: float
    cropping: str = Field(description="작형 (예: 촉성재배)")
    plant_date: date
    harvest_start: date
    harvest_end: date
    price_per_kg: int = Field(description="수확 기간 평균 예상 도매가 (원/kg)")
    error_pct: int = Field(description="예상가 오차 범위 (±%)")
    yield_t: float = Field(description="예상 수확량 (톤)")
    revenue: int = Field(description="예상 매출 (원)")
    cost: int = Field(description="생산비 (원)")
    margin: int = Field(description="마진 = 매출 − 생산비 (원)")
    margin_rate: float = Field(description="마진률 (%) = 마진 ÷ 매출")
    margin_per_pyeong: int
    yield_t_per_10a: float
    cost_per_10a: int = Field(description="10a당 생산비 (원)")


class Unavailable(BaseModel):
    crop: str
    crop_name: str
    emoji: str
    land_type: LandType
    reason: str
    next_plant_date: date | None = None
    next_cropping: str | None = None


class RecommendCropsResponse(BaseModel):
    start_date: date
    results: list[Option] = Field(description="심을 수 있는 작물, 마진 높은 순")
    unavailable: list[Unavailable]
    model_version: str


class PlantingDatesRequest(BaseModel):
    crop: str = Field(examples=["tomato"])
    area_pyeong: float = Field(gt=0, le=1_000_000, examples=[600])


class PlantingPoint(BaseModel):
    plant_date: date
    option: Option | None = Field(description="그 주에 심을 수 없으면 null")


class PlantingDatesResponse(BaseModel):
    crop: CropOut
    note: str | None = Field(None, description="다년생 작물 안내 (이때 points 는 비어 있음)")
    best: Option | None = Field(description="마진률이 가장 높은 심는 날 (비슷하면 더 가까운 날)")
    top: list[Option] = Field(description="작형마다 가장 좋은 날, 마진률 높은 순")
    points: list[PlantingPoint] = Field(description="앞으로 1년, 주 단위")
    model_version: str


class PricePathPoint(BaseModel):
    date: date
    price: int
    lower: int
    upper: int


class PricePathResponse(BaseModel):
    crop: CropOut
    points: list[PricePathPoint] = Field(description="오늘부터 13개월, 주 단위 예상 도매가와 오차 범위 (원/kg)")
    model_version: str
