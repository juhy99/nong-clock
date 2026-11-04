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
    prev_crop: str | None = Field(None, examples=["상추"], description="이 토지에서 기존에 키우던 작물 (shared/soil_ph.json 의 작물 이름). 없으면 pH 비교 안 함")


class WhereToSell(BaseModel):
    region: Sido = Field("서울", examples=["경기"], description="토지 위치 (시·도). 그 시·도 안 도매시장끼리 비교 (없으면 전국 평균)")
    market: str | None = Field(None, examples=["310101"], description="그 시·도 안에서 특정 시장으로 고정할 때만. 없으면 순이익이 가장 높은 시장")


class RecommendCropsRequest(WhereToSell):
    lands: list[Land] = Field(min_length=1, description="보유 토지 (종류마다 하나)")
    start_date: date = Field(description="농사 시작 날짜. 오늘 ~ 30일 뒤")


class MarketRef(BaseModel):
    code: str = Field(description="도매시장 코드, national = 전국 평균")
    name: str


class MarketResult(MarketRef):
    price_per_kg: int
    revenue: int
    margin: int
    margin_rate: float
    factor: float = Field(description="시장 계수 (전국 평균 = 1)")
    best: bool = Field(False, description="그 시·도 안에서 순이익이 가장 높은 시장")


class PhInfo(BaseModel):
    kind: Literal["lower", "near", "raise", "ok", "unknown"] = Field(description="lower: 0.5 이상 낮춰야 → 맨 아래로 · near: 덜 높음 · raise: 석회로 올리면 됨 · ok · unknown: pH 자료 없음")
    min: float | None = Field(description="이 작물 알맞은 pH 최저")
    max: float | None
    gap: float = Field(description="낮추거나 올려야 하는 양")


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
    market: MarketRef = Field(description="판 도매시장 (시·도 안에서 순이익이 가장 높은 곳)")
    no_market: bool = Field(False, description="시·도 안에 공영 도매시장이 없어 전국 평균으로 계산함")
    prev_crop: str | None = Field(None, description="그 토지의 기존 작물")
    soil_ph: float | None = Field(None, description="기존 작물로 어림한 흙 pH (범위 가운데)")
    ph: PhInfo | None = Field(None, description="흙 pH 비교 (기존 작물이 없으면 null)")
    demoted: bool = Field(False, description="pH 를 낮춰야 해서 순이익과 상관없이 맨 아래로 내림")
    factor: float = Field(description="판 시장 계수 (전국 평균 = 1)")
    price_per_kg: int = Field(description="판 시장의 출하량 가중 평균 예상가 (원/kg)")
    national_price_per_kg: int = Field(description="전국 도매시장 평균 예상가 (원/kg)")
    error_pct: int = Field(description="예상가 오차 범위 (±%) = 모델 검증 오차(WAPE), 작물·수확까지 남은 날 기준")
    reference: Literal["far", "baseline"] | None = Field(None, description="참고용: far 6개월보다 먼 수확 · baseline 기준선보다 나쁜 품목·기간")
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
    market_compare: list[MarketResult] = Field(default_factory=list, description="토지 위치(시·도) 안 도매시장마다 팔았을 때 (없으면 전국 평균 1개)")


class Unavailable(BaseModel):
    crop: str
    crop_name: str
    emoji: str
    land_type: LandType
    reason: str
    next_plant_date: date | None = None
    next_cropping: str | None = None


class Excluded(BaseModel):
    crop: str
    crop_name: str
    emoji: str
    land_type: LandType
    kind: Literal["perennial", "land", "season", "ph", "low"] = Field(description="다년생 · 토지 없음 · 심는 시기 아님 · pH 때문에 내림 · 상위에 못 듦")
    reason: str = Field(description="화면에 그대로 보여 줄 한 줄 이유")


class RecommendCropsResponse(BaseModel):
    start_date: date
    region: str
    markets: list[MarketRef] = Field(description="비교한 도매시장 (토지 위치 안, 없으면 전국 평균)")
    no_market: bool = Field(False, description="시·도 안에 공영 도매시장이 없어 전국 평균으로 계산함")
    results: list[Option] = Field(description="심을 수 있는 작물: 순이익 높은 순, pH 를 낮춰야 하는 작물은 맨 아래")
    excluded: list[Excluded] = Field(default_factory=list, description="추천 상위(3위 안)에 없는 작물과 이유 — 작물 정보 탭")
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
    points: list[PricePathPoint] = Field(description="오늘부터 13개월, 주 단위 전국 공영도매 예상 경매 단가와 모델 검증 오차 범위 (원/kg). 시장별 값은 × 시장 계수")
    model_version: str


class CroppingInfo(BaseModel):
    name: str
    plant_from: tuple[int, int] = Field(description="심는 기간 시작 (월, 일)")
    plant_to: tuple[int, int]
    days_to_harvest: int
    harvest_days: int
    storage_days: int
    multi_harvest: bool
    yield_t_per_10a: float
    cost_per_10a: int
    source: Literal["rda", "est"]


class SoilPhOut(BaseModel):
    name: str
    min: float | None
    max: float | None
    memo: str


class CropInfoResponse(BaseModel):
    crop: CropOut
    note: str | None = Field(None, description="다년생 안내")
    marketable_rate: float
    rda: RdaRef | None
    soil_ph: SoilPhOut | None = Field(None, description="알맞은 흙 pH (팀 자료)")
    croppings: list[CroppingInfo]
    model_version: str
