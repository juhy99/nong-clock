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


Sido = Literal["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]


class Land(BaseModel):
    type: LandType = Field(examples=["house"], description="open 노지 · house 시설 · paddy 논 · orchard 과수원")
    area_pyeong: float = Field(gt=0, le=1_000_000, examples=[600], description="평수")
    land_rent: float = Field(0, ge=0, le=1_000_000, description="이번 작기 토지 임차료 (만원) — 경영비에 그대로 더함")
    machine_rent: float = Field(0, ge=0, le=1_000_000, description="이번 작기 농기계·시설 임차료 (만원) — 경영비에 그대로 더함")


class WhereToSell(BaseModel):
    region: Sido = Field("서울", examples=["충남"], description="토지 위치 (시·도)")
    market: str | None = Field(None, examples=["340101"], description="팔 도매시장 코드. 없으면 토지 위치에서 가장 가까운 시장, national = 전국 평균")


class RecommendCropsRequest(WhereToSell):
    lands: list[Land] = Field(min_length=1, description="보유 토지 (종류마다 하나)")
    start_date: date = Field(description="농사 시작 날짜. 오늘 ~ 30일 뒤")


class MarketRef(BaseModel):
    code: str
    name: str
    km: int | None = Field(None, description="토지 위치(시·도 중심)에서 거리")


class MarketResult(MarketRef):
    price_per_kg: int
    revenue: int
    margin: int
    margin_rate: float
    factor: float = Field(description="시장 계수 (전국 평균 = 1)")


class Shipment(BaseModel):
    month: str = Field(examples=["2027-01"])
    t: float = Field(description="그 달 판매량 (톤)")
    price_per_kg: int
    revenue: int


class RdaRef(BaseModel):
    row: str = Field(description="농진청 2024 농산물소득조사 표의 행 이름")
    revenue: int = Field(description="10a당 총수입 (원)")
    cost: int = Field(description="10a당 경영비 (원)")
    income: int = Field(description="10a당 소득 (원)")
    kg: int
    price: int


class Per10a(BaseModel):
    revenue: int
    cost: int = Field(description="임대료 뺀 전국 평균 경영비")
    income: int


class Option(BaseModel):
    crop: str
    crop_name: str
    emoji: str
    land_type: LandType
    area_pyeong: float
    cropping: str = Field(description="작형 (예: 촉성재배)")
    plant_date: date
    harvest_start: date = Field(description="첫 수확")
    harvest_end: date = Field(description="마지막 수확")
    days_to_harvest: int
    harvest_days: int = Field(description="첫 수확 ~ 마지막 수확 일수")
    multi_harvest: bool = Field(description="한 포기에서 여러 번 따는 작형 (토마토·오이 등)")
    storage_days: int = Field(description="수확 뒤 저온 저장으로 팔 수 있는 일수 (추정)")
    storage_end: date
    region: str
    market: MarketRef = Field(description="판 도매시장")
    factor: float = Field(description="판 시장 계수 (전국 평균 = 1)")
    price_per_kg: int = Field(description="판 시장의 출하량 가중 평균 예상가 (원/kg)")
    national_price_per_kg: int = Field(description="전국 도매시장 평균 예상가 (원/kg)")
    error_pct: int = Field(description="예상가 오차 범위 (±%)")
    yield_t: float = Field(description="예상 수확량 (톤)")
    sellable_t: float = Field(description="판매량 = 수확량 × 상품화율 (톤)")
    marketable_rate: float = Field(description="상품화율. 조사표 작물은 1 (조사표 가격에 이미 반영)")
    revenue: int = Field(description="예상 매출 = Σ 월별 판매량 × 월별 예상가 (원)")
    base_cost: int = Field(description="전국 평균 경영비 × 면적 (원)")
    land_rent: int
    machine_rent: int
    cost: int = Field(description="총경영비 = base_cost + 임대료 (원)")
    margin: int = Field(description="예상 순이익 = 매출 − 총경영비 (원)")
    margin_rate: float = Field(description="마진률 (%) = 순이익 ÷ 매출")
    margin_per_pyeong: int
    margin_low: int = Field(description="가격이 오차만큼 내렸을 때 순이익")
    margin_high: int = Field(description="가격이 오차만큼 올랐을 때 순이익")
    national_margin: int = Field(description="전국 평균 가격으로 팔았을 때 순이익")
    yield_t_per_10a: float
    cost_per_10a: int = Field(description="10a당 경영비 (원)")
    source: Literal["rda", "est"] = Field(description="수량·경영비 출처: rda 농진청 조사표, est 추정")
    rda: RdaRef | None = Field(description="비교용 농진청 조사표 10a당 값 (없으면 null)")
    per_10a: Per10a = Field(description="이 계획을 10a로 환산 (비교용)")
    shipments: list[Shipment] = Field(description="달마다 판매량·예상가·매출")
    market_compare: list[MarketResult] = Field(default_factory=list, description="가까운 시장 4곳 + 서울가락 + 전국 평균에 팔았을 때")


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
    region: str
    market: MarketRef
    results: list[Option] = Field(description="심을 수 있는 작물, 마진 높은 순")
    unavailable: list[Unavailable]
    model_version: str


class PlantingDatesRequest(WhereToSell):
    crop: str = Field(examples=["tomato"])
    area_pyeong: float = Field(gt=0, le=1_000_000, examples=[600])
    land_rent: float = Field(0, ge=0, le=1_000_000, description="이번 작기 토지 임차료 (만원)")
    machine_rent: float = Field(0, ge=0, le=1_000_000, description="이번 작기 농기계·시설 임차료 (만원)")


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
    points: list[PricePathPoint] = Field(description="오늘부터 13개월, 주 단위 전국 평균 예상 도매가와 오차 범위 (원/kg). 시장별 값은 × 시장 계수")
    model_version: str
