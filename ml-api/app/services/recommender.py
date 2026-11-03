"""작물 추천 계산.

순이익(마진) = 예상 매출 − 총경영비
- 예상 매출 = Σ(주별 출하량 × 그 주 예상가) — 수확 기간(첫 수확 ~ 마지막 수확)을 주 단위로 나눠 출하 비중(ship_weight)만큼 판다
- 출하량 합계 = 10a당 수량 × 면적(평 ÷ 302.5) × 상품화율
- 예상가 = 전국 도매시장 평균 예측(월별 예상가를 날짜로 이음) × 고른 도매시장 계수(markets.market_factor)
- 총경영비 = 10a당 경영비(전국 평균) × 면적 + 사용자가 넣은 임대료(토지·농기계·시설, 그대로 더함)
- 가격 하락·상승 시나리오 = 예상가 ∓ 예측 오차 범위(error_pct)
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.crop_calendar import CROPS, Crop, Cropping, error_pct, ship_weight
from app.core.markets import GARAK, MARKETS, market_factor, markets_near

PYEONG_PER_10A = 302.5
WEEKS_AHEAD = 53  # 심는 날 비교 범위: 앞으로 1년(주 단위)
TIE_PCT = 0.5     # 마진률이 이만큼 안쪽으로 비슷하면 더 가까운 날을 고른다
COMPARE_NEAR = 4  # 시장 비교: 가까운 시장 수 (+ 서울가락 + 전국 평균)


@dataclass
class Rent:
    land: float = 0.0     # 만원
    machine: float = 0.0  # 만원


@dataclass
class Option:
    crop: Crop
    cropping: Cropping
    plant: date
    harvest_start: date
    harvest_end: date
    area_pyeong: float
    total_t: float
    sell_t: float
    national_revenue: float          # 전국 평균 가격으로 판 매출
    base_cost: float
    land_rent: float
    machine_rent: float
    months_ahead: float
    shipments: list[tuple[str, float, float]] = field(default_factory=list)  # (YYYY-MM, 톤, 전국 평균가 매출)
    market: str = "national"
    factor: float = 1.0

    @property
    def revenue(self) -> float:
        return self.national_revenue * self.factor

    @property
    def cost(self) -> float:
        return self.base_cost + self.land_rent + self.machine_rent

    @property
    def margin(self) -> float:
        return self.revenue - self.cost

    @property
    def margin_rate(self) -> float:
        return self.margin / self.revenue * 100 if self.revenue else 0.0

    @property
    def price(self) -> float:
        return self.revenue / (self.sell_t * 1000) if self.sell_t else 0.0

    @property
    def error_pct(self) -> int:
        return error_pct(self.months_ahead)

    def at(self, market: str) -> "Option":
        """같은 계획을 다른 도매시장에 팔았을 때 (매출만 시장 계수만큼 바뀐다)"""
        o = Option(**{k: getattr(self, k) for k in self.__dataclass_fields__})
        o.market, o.factor = market, market_factor(self.crop.code, market)
        return o


def price_on(crop: Crop, d: date, today: date) -> float:
    """1~12월 예상가를 날짜 사이로 이어서 읽는다 (이번 달 15일 = 이번 달 값)."""
    m = (d - date(today.year, today.month, 15)).days / 30.44
    i = int(m // 1)
    f = m - i
    p = crop.monthly_price
    def g(k: int) -> int:
        return p[(today.month - 1 + k) % 12]
    return g(i) * (1 - f) + g(i + 1) * f


def in_window(d: date, c: Cropping) -> bool:
    k, s, e = (d.month, d.day), c.plant_from, c.plant_to
    return s <= k <= e if s <= e else (k >= s or k <= e)


def cropping_on(crop: Crop, d: date) -> Cropping | None:
    return next((c for c in crop.croppings if in_window(d, c)), None)


def next_window(crop: Crop, after: date) -> tuple[date, Cropping] | None:
    for k in range(1, 370):
        d = after + timedelta(days=k)
        c = cropping_on(crop, d)
        if c:
            return d, c
    return None


def evaluate(crop: Crop, c: Cropping, plant: date, area_pyeong: float, today: date, rent: Rent | None = None, market: str | None = None) -> Option:
    rent = rent or Rent()
    h0 = plant + timedelta(days=c.days_to_harvest)
    h1 = h0 + timedelta(days=c.harvest_days)
    a10 = area_pyeong / PYEONG_PER_10A
    weeks, d = [], h0
    while d <= h1:
        weeks.append(d)
        d += timedelta(days=7)
    ws = [ship_weight(i / (len(weeks) - 1) if len(weeks) > 1 else 0, c.multi_harvest) for i in range(len(weeks))]
    wsum = sum(ws)
    total_t = c.yield_t_per_10a * a10
    sell_t = total_t * crop.marketable
    ship: dict[str, list[float]] = {}
    revenue = 0.0
    for d, w in zip(weeks, ws):
        t = sell_t * w / wsum
        won = t * 1000 * price_on(crop, d, today)
        revenue += won
        m = ship.setdefault(d.strftime("%Y-%m"), [0.0, 0.0])
        m[0] += t
        m[1] += won
    o = Option(
        crop=crop, cropping=c, plant=plant, harvest_start=h0, harvest_end=h1, area_pyeong=area_pyeong,
        total_t=total_t, sell_t=sell_t, national_revenue=revenue, base_cost=c.cost_manwon_per_10a * 10_000 * a10,
        land_rent=rent.land * 10_000, machine_rent=rent.machine * 10_000, months_ahead=(h0 - today).days / 30.44,
        shipments=[(k, v[0], v[1]) for k, v in ship.items()],
    )
    return o.at(market) if market else o


def pick_market(region: str, market: str | None) -> str:
    """고른 시장이 없거나 모르는 코드면 토지 위치에서 가장 가까운 시장"""
    return market if market in MARKETS or market == "national" else markets_near(region)[0][0].code


def compare_markets(o: Option, region: str) -> list[tuple[str, str, int | None, Option]]:
    """[(코드, 이름, 거리 km, 그 시장에 팔았을 때)] — 가까운 시장 4곳 + 서울가락 + 전국 평균"""
    near = markets_near(region)
    picks = near[:COMPARE_NEAR]
    if all(m.code != GARAK for m, _ in picks):
        picks = picks + [next(t for t in near if t[0].code == GARAK)]
    out = [(m.code, m.name, k, o.at(m.code)) for m, k in picks]
    return out + [("national", "전국 평균", None, o.at("national"))]


def recommend_crops(lands: dict[str, float], rents: dict[str, Rent], start: date, today: date, market: str) -> tuple[list[Option], list[tuple[Crop, str, tuple[date, Cropping] | None]]]:
    """토지 종류별 평수·임대료 → (심을 수 있는 작물 순이익 높은 순, 지금 못 심는 작물과 이유)"""
    ok, off = [], []
    for crop in CROPS.values():
        area = lands.get(crop.land_type, 0)
        if area <= 0:
            continue
        if crop.perennial_note:
            off.append((crop, crop.perennial_note, None))
            continue
        c = cropping_on(crop, start)
        if c:
            ok.append(evaluate(crop, c, start, area, today, rents.get(crop.land_type), market))
        else:
            off.append((crop, "심는 시기가 아니에요", next_window(crop, start)))
    ok.sort(key=lambda o: o.margin, reverse=True)
    return ok, off


def better(a: Option | None, b: Option, metric: str = "rate") -> Option:
    if a is None:
        return b
    va, vb = (a.margin_rate, b.margin_rate) if metric == "rate" else (a.margin, b.margin)
    tol = TIE_PCT if metric == "rate" else max(1.0, abs(va) * 0.01)
    return b if vb > va + tol else a


def planting_dates(crop: Crop, area_pyeong: float, today: date, rent: Rent | None = None, market: str = "national") -> tuple[list[tuple[date, Option | None]], Option | None, list[Option]]:
    """앞으로 1년, 주 단위로 심는 날별 결과 → (날짜별 결과, 마진률 최고, 작형별 최고 TOP)"""
    points = []
    for k in range(WEEKS_AHEAD):
        d = today + timedelta(days=7 * k)
        c = cropping_on(crop, d)
        points.append((d, evaluate(crop, c, d, area_pyeong, today, rent, market) if c else None))
    best = None
    per_cropping: dict[str, Option | None] = {}
    for _, o in points:
        if o is None:
            continue
        best = better(best, o)
        per_cropping[o.cropping.name] = better(per_cropping.get(o.cropping.name), o)
    top = sorted((o for o in per_cropping.values() if o), key=lambda o: o.margin_rate, reverse=True)
    return points, best, top


__all__ = ["Option", "Rent", "compare_markets", "error_pct", "evaluate", "pick_market", "planting_dates", "recommend_crops", "price_on"]
