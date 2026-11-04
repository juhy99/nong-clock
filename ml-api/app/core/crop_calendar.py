"""작물 추천용 작물 달력.

작형마다 심는 기간, 심고 첫 수확까지 일수, 수확이 이어지는 일수(첫 수확 ~ 마지막 수확), 10a당 수량·경영비, 수확 뒤 보관 일수를 둔다.
- 10a당 수량·경영비·가격 수준: 농촌진흥청 2024년도 농산물소득조사 (RDA). 조사표 행과 맞는 작형은 source="rda",
  나머지 작형과 조사표에 없는 작물(양파·봄동·마늘·쌀·콩)은 추정값 source="est"
- 심는 시기·수확 기간: 농사로 재배력 작형 기준. 보관: 알맞은 저온 저장에서 팔 수 있는 기간 (추정)
- monthly_price: 1~12월 예상 도매가(원/kg) 모양(추정). 조사표가 있는 작물은 대표 작형(첫 작형)의 출하량 가중 평균가가
  조사표 농가수취가격과 같도록 calibrate() 로 맞춘다. 장기 가격 모델이 붙으면 그 예측으로 바꾼다.
- 프론트 예비 데이터 frontend/src/mocks/recommend.js 와 값이 같다 (바꿀 때 둘 다 고칠 것)
"""

import math
from dataclasses import dataclass, field, replace
from datetime import date, timedelta

LAND_TYPES = {"open": "노지", "house": "시설", "paddy": "논", "orchard": "과수원"}


@dataclass(frozen=True)
class Rda:
    """농진청 2024 조사표 10a당 값 (천원 · kg · 원/kg)"""
    row: str
    revenue: int
    cost: int
    income: int
    kg: int
    price: int


RDA: dict[str, Rda] = {
    "tomato": Rda("토마토(토경)", 20510, 9768, 10741, 6226, 3294),
    "cucumber": Rda("시설오이", 25184, 12300, 12884, 10505, 2397),
    "lettuce": Rda("시설상추", 11629, 6609, 5020, 3315, 3508),
    "paprika": Rda("시설파프리카", 40882, 29421, 11461, 11233, 3640),
    "strawberry": Rda("딸기(토경)", 26307, 15621, 10686, 2893, 9094),
    "green_onion": Rda("대파", 4570, 1915, 2655, 3821, 1196),
    "spinach": Rda("노지시금치", 3787, 1205, 2581, 978, 3870),
    "napa_cabbage": Rda("가을배추", 4137, 1534, 2603, 6155, 672),
    "potato": Rda("봄감자", 2693, 1444, 1250, 2263, 1190),
    "carrot": Rda("당근", 6275, 2462, 3813, 3542, 1772),
}
RDA_ALL = {"napa_cabbage", "potato"}  # 작형마다 조사표 행이 따로 있음 (봄·가을배추, 봄·가을감자)
# 상품화율 (추정). 조사표 가격은 상품·비품을 섞은 평균 수취가라 조사표 작물은 1 (두 번 빼지 않음)
MARKETABLE = {"onion": 0.93, "bomdong": 0.9, "garlic": 0.9, "rice": 1.0, "soybean": 0.95}


@dataclass(frozen=True)
class Cropping:
    name: str
    plant_from: tuple[int, int]  # (월, 일)
    plant_to: tuple[int, int]
    days_to_harvest: int   # 심고 첫 수확까지
    harvest_days: int      # 첫 수확 ~ 마지막 수확
    yield_t_per_10a: float
    cost_manwon_per_10a: float  # 경영비 (전국 평균)
    storage_days: int = 0
    source: str = "est"

    @property
    def multi_harvest(self) -> bool:  # 한 포기에서 여러 번 따는 작형
        return self.harvest_days > 30


@dataclass(frozen=True)
class Crop:
    code: str
    name: str
    emoji: str
    land_type: str
    monthly_price: tuple[int, ...] = ()  # 1~12월
    croppings: tuple[Cropping, ...] = ()
    perennial_note: str | None = None  # 다년생이면 안내 문구 (날짜별 비교 안 함)
    rda: Rda | None = None
    marketable: float = 1.0
    tags: tuple[str, ...] = field(default=())


def _c(name, pf, pt, dth, hd, yld, cost, store):
    return Cropping(name, pf, pt, dth, hd, yld, cost, store)


def _crop(code, name, emoji, land, price, croppings=(), note=None) -> Crop:
    rda = RDA.get(code)
    cl = tuple(replace(c, source="rda" if code in RDA_ALL or (rda and i == 0) else "est") for i, c in enumerate(croppings))
    return Crop(code, name, emoji, land, tuple(price), cl, note, rda, 1.0 if rda else MARKETABLE.get(code, 0.9))


def ship_weight(t: float, multi: bool) -> float:
    """수확 기간 안 출하 비중 (t = 0~1). 여러 번 따는 작물은 처음·끝에 적고 가운데 많게"""
    if not multi:
        return 1.0
    return 0.4 + 2 * t if t < 0.3 else 1.0 if t < 0.75 else 1 - 1.6 * (t - 0.75)


def _calibrate(c: Crop) -> Crop:
    """대표 작형을 심는 기간 가운데 날 심었을 때 출하량 가중 평균가 = 조사표 농가수취가격 이 되게 월별 가격을 늘리거나 줄인다"""
    if not c.rda or not c.monthly_price:
        return c
    w = c.croppings[0]
    mid = math.floor(((w.plant_to[0] - w.plant_from[0] + 12) % 12) * 15 + (w.plant_to[1] - w.plant_from[1]) / 2 + 0.5)  # JS Math.round 와 같게
    plant = date(2026, *w.plant_from) + timedelta(days=mid)
    h0 = plant + timedelta(days=w.days_to_harvest)
    h1 = h0 + timedelta(days=w.harvest_days)
    pts, d = [], h0
    while d <= h1:
        pts.append(d)
        d += timedelta(days=7)
    sw = sp = 0.0
    for i, d in enumerate(pts):
        wt = ship_weight(i / (len(pts) - 1) if len(pts) > 1 else 0, w.multi_harvest)
        sw += wt
        sp += wt * c.monthly_price[d.month - 1]
    k = c.rda.price / (sp / sw)
    return replace(c, monthly_price=tuple(int((v * k / 10) + 0.5) * 10 for v in c.monthly_price))


CROPS: dict[str, Crop] = {
    c.code: _calibrate(c)
    for c in [
        _crop("tomato", "토마토", "🍅", "house", (3300, 3200, 3000, 2700, 2200, 1800, 2200, 3300, 4200, 4500, 3900, 3500), (
            _c("촉성재배", (9, 21), (11, 20), 80, 150, 6.2, 977, 10), _c("반촉성재배", (1, 11), (2, 20), 75, 90, 4.5, 800, 10),
            _c("억제재배", (7, 11), (8, 10), 60, 80, 3.5, 650, 10))),
        _crop("cucumber", "오이", "🥒", "house", (3000, 2800, 2500, 2000, 1600, 1500, 1900, 2600, 2800, 2300, 2200, 2800), (
            _c("촉성재배", (10, 11), (12, 10), 40, 110, 10.5, 1230, 7), _c("반촉성재배", (1, 11), (2, 28), 35, 90, 8, 950, 7),
            _c("억제재배", (8, 21), (9, 20), 30, 70, 6, 750, 7))),
        _crop("lettuce", "상추", "🥬", "house", (3600, 3200, 2800, 2500, 2400, 3000, 4200, 5200, 4800, 3800, 3300, 3500), (
            _c("겨울재배", (10, 21), (12, 10), 40, 60, 3.0, 600, 10), _c("봄재배", (2, 1), (3, 31), 35, 45, 2.6, 500, 10),
            _c("가을재배", (8, 21), (9, 20), 30, 45, 2.4, 480, 10))),
        _crop("paprika", "파프리카", "🫑", "house", (4000, 3800, 3500, 3200, 3000, 3200, 3600, 4200, 4500, 4000, 3800, 4000), (
            _c("장기재배", (8, 1), (8, 31), 90, 240, 11.2, 2942, 21),)),
        _crop("strawberry", "딸기", "🍓", "house", (10500, 9500, 8000, 6500, 5500, 6000, 7000, 8000, 9000, 11000, 13000, 12500), (
            _c("촉성재배", (9, 1), (9, 25), 75, 165, 2.9, 1562, 5),)),
        _crop("green_onion", "대파", "🧅", "open", (1300, 1400, 1500, 1400, 1200, 1100, 1100, 1200, 1300, 1100, 1000, 1200), (
            _c("월동재배", (7, 11), (8, 31), 140, 110, 3.8, 192, 14), _c("봄재배", (3, 21), (5, 31), 120, 60, 3.5, 180, 14))),
        _crop("spinach", "시금치", "🥬", "open", (3200, 3000, 3300, 3500, 3800, 4500, 6000, 7000, 6000, 4500, 3500, 3300), (
            _c("가을재배", (8, 21), (9, 30), 40, 20, 1.0, 121, 10), _c("월동재배", (10, 1), (11, 15), 90, 60, 1.0, 121, 10),
            _c("봄재배", (3, 1), (4, 15), 40, 15, 0.9, 115, 10))),
        _crop("onion", "양파", "🧅", "open", (1100, 1150, 1200, 1250, 1000, 900, 950, 1000, 1050, 1100, 1150, 1100), (
            _c("보통재배", (10, 21), (11, 20), 200, 20, 6.6, 280, 210),)),
        _crop("bomdong", "봄동", "🥬", "open", (1600, 1500, 1400, 1300, 1300, 1300, 1300, 1300, 1400, 1500, 1600, 1700), (
            _c("월동재배", (9, 1), (10, 20), 90, 80, 2.0, 90, 10),)),
        _crop("garlic", "마늘", "🧄", "open", (6900, 6950, 7000, 7050, 7100, 6800, 6200, 6000, 6300, 6500, 6700, 6800), (
            _c("난지형", (9, 21), (10, 31), 235, 20, 1.4, 300, 240),)),
        _crop("napa_cabbage", "배추", "🥬", "open", (800, 750, 800, 900, 700, 600, 900, 1100, 1000, 800, 600, 700), (
            _c("가을재배", (8, 21), (9, 10), 70, 20, 6.2, 153, 60), _c("봄재배", (3, 21), (4, 30), 60, 15, 7.1, 134, 20))),
        _crop("potato", "감자", "🥔", "open", (1300, 1350, 1400, 1450, 1300, 1100, 1000, 1000, 1050, 1100, 1200, 1250), (
            _c("봄재배", (3, 1), (3, 31), 100, 20, 2.3, 144, 120), _c("가을재배", (8, 11), (8, 31), 100, 15, 1.8, 168, 120))),
        _crop("carrot", "당근", "🥕", "open", (1650, 1700, 1800, 1900, 1950, 1850, 1700, 1500, 1400, 1500, 1600, 1600), (
            _c("봄재배", (3, 11), (4, 20), 110, 20, 3.5, 246, 120), _c("가을재배", (7, 11), (8, 10), 110, 30, 3.5, 246, 120))),
        _crop("rice", "쌀", "🌾", "paddy", (2450, 2450, 2480, 2500, 2500, 2520, 2550, 2550, 2560, 2400, 2350, 2400), (
            _c("모내기", (5, 11), (6, 10), 130, 20, 0.52, 72, 365),)),
        _crop("soybean", "콩", "🫘", "paddy", (5500, 5500, 5600, 5600, 5700, 5700, 5800, 5800, 5800, 5500, 5300, 5400), (
            _c("논콩", (6, 1), (6, 30), 125, 15, 0.23, 50, 365),)),
        _crop("apple", "사과", "🍎", "orchard", (), note="나무를 심고 3~5년 뒤부터 매년 9~11월 수확"),
        _crop("pear", "배", "🍐", "orchard", (), note="나무를 심고 4~5년 뒤부터 매년 8~11월 수확"),
        _crop("peach", "복숭아", "🍑", "orchard", (), note="나무를 심고 3~4년 뒤부터 매년 6~9월 수확"),
    ]
}

# 가격 오차 범위(%)는 모델 검증 오차(품목·예측 기간별 WAPE) — app/core/accuracy.py
