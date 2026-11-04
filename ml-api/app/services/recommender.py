"""작물 추천 계산.

순이익(마진) = 예상 매출 − 총경영비
- 예상 매출 = Σ(주별 출하량 × 그 주 예상가) — 수확 기간(첫 수확 ~ 마지막 수확)을 주 단위로 나눠 출하 비중(ship_weight)만큼 판다
- 출하량 합계 = 10a당 수량 × 면적(평 ÷ 302.5) × 상품화율
- 예상가 = 전국 도매시장 평균 예측(월별 예상가를 날짜로 이음) × 도매시장 계수(markets.market_factor)
- 팔 시장: 토지 위치(시·도) 안의 공영 도매시장 중 순이익이 가장 높은 곳 (시장이 없는 시·도는 전국 평균).
  11/4 팀 결정: 수확한 지역 안의 도매시장에서 판다고 가정하고, 운송비와 유통 마진은 계산하지 않는다
- 기존 작물(토지마다) → 흙 pH 어림. 흙 pH 가 후보 작물 최고값보다 0.5 이상 높으면 순이익과 상관없이 맨 아래로 (soil_ph.py)
- 총경영비 = 10a당 경영비(전국 평균) × 면적 + 사용자가 넣은 임대료(토지·농기계·시설, 그대로 더함)
- 가격 하락·상승 시나리오 = 예상가 ∓ 예측 오차 범위(error_pct)
"""

import math
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core import accuracy
from app.core.crop_calendar import CROPS, LAND_TYPES, Crop, Cropping, ship_weight
from app.core.markets import NATIONAL, market_factor, markets_in_sido
from app.core.soil_ph import SoilPh, ph_check, soil_ph_from_prev

PYEONG_PER_10A = 302.5
WEEKS_AHEAD = 53  # 심는 날 비교 범위: 앞으로 1년(주 단위)
TIE_PCT = 0.5     # 마진률이 이만큼 안쪽으로 비슷하면 더 가까운 날을 고른다
TOP_N = 3         # 작물 정보 탭 "추천 상위" 기준


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
    prev_crop: str | None = None      # 그 토지의 기존 작물 (조건표 이름)
    soil_ph: float | None = None      # 기존 작물로 어림한 흙 pH
    ph: tuple[str, SoilPh | None, float] | None = None  # soil_ph.ph_check 결과

    @property
    def demoted(self) -> bool:
        return bool(self.ph and self.ph[0] == "lower")

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
        """수확 시작까지 남은 날의 예측 오차(±%) = 모델 검증 WAPE (작물·기간별)"""
        return math.floor(accuracy.error_pct(self.crop.code, max(1, round(self.months_ahead * 30.44))) + 0.5)

    @property
    def reference(self) -> str | None:
        return accuracy.reference_of(self.crop.code, max(1, round(self.months_ahead * 30.44)))

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


def sido_markets(region: str) -> tuple[list[str], bool]:
    """(그 시·도 안 시장 코드들, 시장이 없어 전국 평균을 쓰는지) — 다른 지역 시장은 섞지 않는다"""
    here = [m.code for m in markets_in_sido(region)]
    return (here, False) if here else ([NATIONAL], True)


def compare_markets(o: Option, region: str) -> list[Option]:
    """그 시·도 안 시장마다 팔았을 때"""
    codes, _ = sido_markets(region)
    return [o.at(c) for c in codes]


def at_best_market(o: Option, region: str, market: str | None = None) -> Option:
    """시·도 안 시장 중 순이익이 가장 높은 곳 (market 을 주고 그 시·도 안이면 그 시장)"""
    opts = compare_markets(o, region)
    forced = next((x for x in opts if x.market == market), None)
    return forced or max(opts, key=lambda x: x.margin)


def apply_soil(o: Option, prev: str | None) -> Option:
    o.prev_crop = prev
    o.soil_ph = soil_ph_from_prev(prev)
    o.ph = ph_check(o.crop.code, o.soil_ph)
    return o


def sort_options(opts: list[Option]) -> list[Option]:
    """pH 를 낮춰야 하는 작물은 맨 아래, 나머지는 순이익 높은 순"""
    return sorted(opts, key=lambda o: (o.demoted, -o.margin))


def recommend_crops(
    lands: dict[str, float], rents: dict[str, Rent], start: date, today: date, region: str,
    market: str | None = None, prevs: dict[str, str | None] | None = None,
) -> tuple[list[Option], list[tuple[Crop, str, tuple[date, Cropping] | None]]]:
    """토지 종류별 평수·임대료·기존 작물 → (심을 수 있는 작물 순서대로, 지금 못 심는 작물과 이유)"""
    prevs = prevs or {}
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
            o = evaluate(crop, c, start, area, today, rents.get(crop.land_type))
            ok.append(apply_soil(at_best_market(o, region, market), prevs.get(crop.land_type)))
        else:
            off.append((crop, "심는 시기가 아니에요", next_window(crop, start)))
    return sort_options(ok), off


def _ten_day(md: tuple[int, int]) -> str:
    m, d = md
    return f"{m}월 {'상순' if d <= 10 else '중순' if d <= 20 else '하순'}"


def excluded(ok: list[Option], lands: dict[str, float], start: date) -> list[tuple[Crop, str, str]]:
    """추천 상위(TOP_N)에 없는 작물마다 (작물, 이유 종류, 한 줄 이유). 종류: perennial · land · season · ph · low"""
    owned = [k for k, v in lands.items() if v > 0]
    owned_txt = "·".join(LAND_TYPES[k] for k in LAND_TYPES if k in owned) or "없음"
    rank = {o.crop.code: (i, o) for i, o in enumerate(ok)}
    out = []
    for crop in CROPS.values():
        if crop.code in rank:
            i, o = rank[crop.code]
            if o.demoted:
                kind, p, gap = o.ph
                out.append((crop, "ph", f"심을 수는 있지만 {LAND_TYPES[crop.land_type]} 토지 흙(기존 작물 {o.prev_crop} 기준 pH 약 {o.soil_ph})이 "
                                       f"알맞은 pH {p.min}~{p.max}보다 {gap} 높아서 맨 아래({i + 1}위)로 내렸어요."))
            elif i >= TOP_N:
                out.append((crop, "low", f"심을 수는 있지만 예상 마진률이 {round(o.margin_rate)}%로, 추천 상위({TOP_N}위 안)에 들지 못했어요. ({len(ok)}개 중 {i + 1}위)"))
            continue
        if crop.perennial_note:
            out.append((crop, "perennial", f"다년생 작물이라 날짜별 추천을 하지 않아요. {crop.perennial_note}"))
        elif crop.land_type not in owned:
            out.append((crop, "land", f"{LAND_TYPES[crop.land_type]} 토지에서만 재배할 수 있어요. 고른 토지: {owned_txt}"))
        else:
            ws = ", ".join(f"{c.name} {_ten_day(c.plant_from)}~{_ten_day(c.plant_to)}" for c in crop.croppings)
            nxt = next_window(crop, start)
            tail = f" 다음 심는 때: {nxt[0].month}/{nxt[0].day}부터({nxt[1].name})" if nxt else ""
            out.append((crop, "season", f"지금({start.month}월)은 심는 시기가 아니에요. {LAND_TYPES[crop.land_type]} {ws}이에요.{tail}"))
    return out


def better(a: Option | None, b: Option, metric: str = "rate") -> Option:
    if a is None:
        return b
    va, vb = (a.margin_rate, b.margin_rate) if metric == "rate" else (a.margin, b.margin)
    tol = TIE_PCT if metric == "rate" else max(1.0, abs(va) * 0.01)
    return b if vb > va + tol else a


def planting_dates(crop: Crop, area_pyeong: float, today: date, rent: Rent | None = None, region: str = "서울", market: str | None = None) -> tuple[list[tuple[date, Option | None]], Option | None, list[Option]]:
    """앞으로 1년, 주 단위로 심는 날별 결과 → (날짜별 결과, 마진률 최고, 작형별 최고 TOP). 화면에서는 안 쓰지만 API 는 남겨 둠"""
    points = []
    for k in range(WEEKS_AHEAD):
        d = today + timedelta(days=7 * k)
        c = cropping_on(crop, d)
        points.append((d, at_best_market(evaluate(crop, c, d, area_pyeong, today, rent), region, market) if c else None))
    best = None
    per_cropping: dict[str, Option | None] = {}
    for _, o in points:
        if o is None:
            continue
        best = better(best, o)
        per_cropping[o.cropping.name] = better(per_cropping.get(o.cropping.name), o)
    top = sorted((o for o in per_cropping.values() if o), key=lambda o: o.margin_rate, reverse=True)
    return points, best, top


__all__ = ["Option", "Rent", "TOP_N", "at_best_market", "compare_markets", "evaluate", "excluded", "planting_dates", "recommend_crops", "price_on", "sido_markets"]
