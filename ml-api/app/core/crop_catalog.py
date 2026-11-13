"""작물 추천용 작물 표 (11-13) — 저장소 맨 위 shared/crops.json 을 읽는다.

그 파일은 python-ml/crops/build_crop_catalog.py 가 실제 자료로 만든다 (손으로 고치지 않음):
- 심는 때 · 수확 때: 농사로 재배력 (전국 표준 달력, 순 단위라 ±10일)
- 10a당 수량 · 경영비 · 농가 수취가격: 농진청 농산물소득조사 · 통계청 농축산물생산비조사 최근 3개 해 평균 (경영비에서 조사 평균 토지임차료는 뺌)
- farm_ratio: 조사 농가 수취가격 ÷ 같은 해 수확 달 전국 도매 평균가 → 예상 수취가 = 예측 도매가 × 이 비율
- normal: 2021~2025 같은 달 전국 도매 평균(최저·최고) — DB 예측이 없는 날에만 씀
- storage_days: 수확 뒤 저온 저장으로 팔 수 있는 일수 (추정)

심는 날 → 수확 (build_crop_catalog.py 의 규칙과 같음)
- 심고 첫 수확까지 = 심는 기간 첫날에 심으면 days_first, 끝날에 심으면 days_last, 사이는 직선
- 한 번 수확(multi = False): 첫 수확부터 harvest_days(14일) 동안
- 여러 번 수확(multi = True, 과채·딸기·상추 등): 첫 수확부터 수확 기간 끝날(harvest_to)까지
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.shared import load

_DATA = load("crops.json")
LAND_TYPES: dict[str, str] = _DATA["land_types"]
BUILT_AT: str = _DATA["built_at"]
Y0 = 2026  # 달·일 → 해 안 위치 계산용 평년 (윤년 아님)


def _doy(md: tuple[int, int]) -> int:
    m, d = md
    if (m, d) == (2, 29):  # 윤년 2월 29일은 28일로 (계산용 평년에 없음)
        d = 28
    return (date(Y0, m, d) - date(Y0, 1, 1)).days


def _gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """a → b 까지 날 수 (해를 넘기면 +365)"""
    return (_doy(b) - _doy(a)) % 365


def _on_or_after(md: tuple[int, int], d: date) -> date:
    """d 이후(같은 날 포함) 처음 오는 (월, 일)"""
    for y in (d.year, d.year + 1):
        try:
            x = date(y, *md)
        except ValueError:  # 2월 29일
            x = date(y, md[0], 28)
        if x >= d:
            return x
    return date(d.year + 1, *md)


@dataclass(frozen=True)
class Survey:
    """조사표 10a당 값 (원 · kg · 원/kg)"""
    row: str
    source: str
    years: tuple[int, ...]
    revenue: int
    cost: int
    income: int
    kg: int
    price: int
    land_rent: int


@dataclass(frozen=True)
class Cropping:
    name: str
    land: str
    plant_from: tuple[int, int]
    plant_to: tuple[int, int]
    harvest_from: tuple[int, int]
    harvest_to: tuple[int, int]
    days_first: int
    days_last: int
    harvest_days_single: int | None   # 한 번 수확 작형의 수확 일수 (여러 번 수확이면 None)
    multi_harvest: bool
    yield_t_per_10a: float
    cost_per_10a: int                 # 원, 조사 평균 토지임차료 뺌 (사용자가 넣은 임대료를 따로 더함)
    farm_ratio: float | None          # 도매가 → 농가 수취가 (조사 작물은 None: 조사 가격 그대로)
    storage_days: int
    schedule_source: str
    econ_source: str
    estimated: tuple[str, ...]
    survey: Survey

    @property
    def window_days(self) -> int:
        return _gap(self.plant_from, self.plant_to) + 1

    @property
    def days_to_harvest(self) -> int:
        """심는 기간 첫날에 심었을 때 첫 수확까지 (작물 정보 달력용)"""
        return self.days_first

    @property
    def harvest_days(self) -> int:
        """첫 수확 ~ 마지막 수확 (작물 정보 달력용, 심는 기간 첫날 기준)"""
        if not self.multi_harvest:
            return self.harvest_days_single or 14
        return max(7, _gap(self.harvest_from, self.harvest_to))

    @property
    def source(self) -> str:
        """rda: 시기·수량·경영비 모두 조사 자료 · est: 시기에 추정이 들어감"""
        return "est" if "schedule" in self.estimated else "rda"

    def in_window(self, d: date) -> bool:
        return _gap(self.plant_from, (d.month, d.day)) < self.window_days

    def schedule(self, plant: date) -> tuple[date, date]:
        """심는 날 → (첫 수확, 마지막 수확)"""
        f = _gap(self.plant_from, (plant.month, plant.day)) / max(1, self.window_days - 1)
        f = min(1.0, max(0.0, f))
        h0 = plant + timedelta(days=round(self.days_first + f * (self.days_last - self.days_first)))
        if self.multi_harvest:
            h1 = _on_or_after(self.harvest_to, h0 + timedelta(days=7))
            if (h1 - h0).days > 330:  # 수확 기간 끝을 이미 지나 심은 경우 — 1년 넘게 따지는 않음
                h1 = h0 + timedelta(days=max(7, self.harvest_days))
        else:
            h1 = h0 + timedelta(days=self.harvest_days)
        return h0, h1


@dataclass(frozen=True)
class Crop:
    code: str
    name: str
    emoji: str
    land_types: tuple[str, ...]
    price_source: str                 # forecast: 품목 50개 (DB 예측 · 평년 도매가) · survey: 조사 수취가격 그대로 (쌀 · 콩)
    croppings: tuple[Cropping, ...] = ()
    perennial_note: str | None = None
    harvest_months: tuple[int, int] | None = None
    soil_ph_name: str | None = None
    survey: Survey | None = None
    survey_price: int | None = None   # price_source = survey 일 때 kg당 수취가격
    normal_price: tuple[int | None, ...] = ()   # 1~12월 평년 전국 도매가 (원/kg)
    normal_low: tuple[int | None, ...] = ()
    normal_high: tuple[int | None, ...] = ()
    farm_ratio: float | None = None   # 과수(정보만)용
    tags: tuple[str, ...] = field(default=())

    @property
    def land_type(self) -> str:
        """대표 토지 (목록·화면 묶음용) — 여러 토지면 첫 번째"""
        return self.land_types[0]


def _survey(r: dict) -> Survey:
    return Survey(r["row"], r["source"], tuple(r["years"]), int(r["revenue"]), int(r["cost"]), int(r["income"]), int(r["kg"]), int(r["price"]),
                  int(r.get("land_rent") or 0))


def _cropping(x: dict) -> Cropping:
    return Cropping(
        name=x["name"], land=x["land"], plant_from=tuple(x["plant_from"]), plant_to=tuple(x["plant_to"]),
        harvest_from=tuple(x["harvest_from"]), harvest_to=tuple(x["harvest_to"]), days_first=int(x["days_first"]), days_last=int(x["days_last"]),
        harvest_days_single=x["harvest_days"], multi_harvest=bool(x["multi_harvest"]), yield_t_per_10a=float(x["yield_t_per_10a"]),
        cost_per_10a=int(x["cost_per_10a"]), farm_ratio=x.get("farm_ratio"), storage_days=int(x.get("storage_days") or 0),
        schedule_source=x["source"]["schedule"], econ_source=x["source"]["econ"], estimated=tuple(x.get("estimated") or ()), survey=_survey(x["rda"]),
    )


def _crop(c: dict) -> Crop:
    n = c.get("normal") or {}
    return Crop(
        code=c["code"], name=c["name"], emoji=c["emoji"], land_types=tuple(c["land_types"]), price_source=c["price_source"],
        croppings=tuple(_cropping(x) for x in c["croppings"]), perennial_note=c.get("perennial_note"),
        harvest_months=tuple(c["harvest_months"]) if c.get("harvest_months") else None, soil_ph_name=c.get("soil_ph_name"),
        survey=_survey(c["rda"]) if c.get("rda") else None, survey_price=c.get("survey_price"),
        normal_price=tuple(n.get("price") or ()), normal_low=tuple(n.get("low") or ()), normal_high=tuple(n.get("high") or ()),
        farm_ratio=c.get("farm_ratio"),
    )


CROPS: dict[str, Crop] = {c["code"]: _crop(c) for c in _DATA["crops"]}


def ship_weight(t: float, multi: bool) -> float:
    """수확 기간 안 출하 비중 (t = 0~1). 여러 번 따는 작물은 처음·끝에 적고 가운데 많게 (가정)"""
    if not multi:
        return 1.0
    return 0.4 + 2 * t if t < 0.3 else 1.0 if t < 0.75 else 1 - 1.6 * (t - 0.75)


__all__ = ["BUILT_AT", "CROPS", "LAND_TYPES", "Crop", "Cropping", "Survey", "ship_weight"]
