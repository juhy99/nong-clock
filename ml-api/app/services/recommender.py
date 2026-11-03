"""작물 추천 계산.

마진 = 예상 수확량 × 수확기 예상 도매가 − 생산비
- 예상 수확량 = 10a당 수량 × 면적(평 ÷ 302.5)
- 수확기 예상 도매가 = 수확 기간 동안의 예상 도매가 평균 (월별 예상가를 날짜로 이어서 1주 간격으로 평균)
"""

from dataclasses import dataclass
from datetime import date, timedelta

from app.core.crop_calendar import CROPS, Crop, Cropping, error_pct

PYEONG_PER_10A = 302.5
WEEKS_AHEAD = 53  # 심는 날 비교 범위: 앞으로 1년(주 단위)
TIE_PCT = 0.5     # 마진률이 이만큼 안쪽으로 비슷하면 더 가까운 날을 고른다


@dataclass
class Option:
    crop: Crop
    cropping: Cropping
    plant: date
    harvest_start: date
    harvest_end: date
    price: float
    yield_t: float
    revenue: float
    cost: float
    months_ahead: float

    @property
    def margin(self) -> float:
        return self.revenue - self.cost

    @property
    def margin_rate(self) -> float:
        return self.margin / self.revenue * 100 if self.revenue else 0.0


def price_on(crop: Crop, d: date, today: date) -> float:
    """월별 예상가(이번 달 15일 = 첫 값)를 날짜 사이로 이어서 읽는다. 12개월 뒤부터는 같은 모양을 반복한다."""
    m = (d - date(today.year, today.month, 15)).days / 30.44
    i = int(m // 1)
    f = m - i
    p = crop.monthly_price
    return p[i % 12] * (1 - f) + p[(i + 1) % 12] * f


def avg_price(crop: Crop, start: date, end: date, today: date) -> float:
    vals, d = [], start
    while d <= end:
        vals.append(price_on(crop, d, today))
        d += timedelta(days=7)
    return sum(vals) / len(vals)


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


def evaluate(crop: Crop, c: Cropping, plant: date, area_pyeong: float, today: date) -> Option:
    h0 = plant + timedelta(days=c.days_to_harvest)
    h1 = h0 + timedelta(days=c.harvest_days)
    a10 = area_pyeong / PYEONG_PER_10A
    price = avg_price(crop, h0, h1, today)
    yield_t = c.yield_t_per_10a * a10
    return Option(
        crop=crop, cropping=c, plant=plant, harvest_start=h0, harvest_end=h1, price=price, yield_t=yield_t,
        revenue=price * yield_t * 1000, cost=c.cost_manwon_per_10a * 10_000 * a10,
        months_ahead=(h0 - today).days / 30.44,
    )


def recommend_crops(lands: dict[str, float], start: date, today: date) -> tuple[list[Option], list[tuple[Crop, str, tuple[date, Cropping] | None]]]:
    """토지 종류별 평수 → (심을 수 있는 작물 마진 높은 순, 지금 못 심는 작물과 이유)"""
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
            ok.append(evaluate(crop, c, start, area, today))
        else:
            nxt = next_window(crop, start)
            off.append((crop, "심는 시기가 아니에요", nxt))
    ok.sort(key=lambda o: o.margin, reverse=True)
    return ok, off


def better(a: Option | None, b: Option, metric: str = "rate") -> Option:
    if a is None:
        return b
    va, vb = (a.margin_rate, b.margin_rate) if metric == "rate" else (a.margin, b.margin)
    tol = TIE_PCT if metric == "rate" else max(1.0, abs(va) * 0.01)
    return b if vb > va + tol else a


def planting_dates(crop: Crop, area_pyeong: float, today: date) -> tuple[list[tuple[date, Option | None]], Option | None, list[Option]]:
    """앞으로 1년, 주 단위로 심는 날별 결과 → (날짜별 결과, 마진률 최고, 작형별 최고 TOP)"""
    points = []
    for k in range(WEEKS_AHEAD):
        d = today + timedelta(days=7 * k)
        c = cropping_on(crop, d)
        points.append((d, evaluate(crop, c, d, area_pyeong, today) if c else None))
    best = None
    per_cropping: dict[str, Option | None] = {}
    for _, o in points:
        if o is None:
            continue
        best = better(best, o)
        per_cropping[o.cropping.name] = better(per_cropping.get(o.cropping.name), o)
    top = sorted((o for o in per_cropping.values() if o), key=lambda o: o.margin_rate, reverse=True)
    return points, best, top


__all__ = ["Option", "error_pct", "evaluate", "planting_dates", "recommend_crops", "price_on"]
