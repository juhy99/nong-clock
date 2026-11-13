"""작물 추천 계산 (11-13 실제 자료로 바꿈 — 작물 표 shared/crops.json · 가격 DB 예측 표).

순이익(마진) = 예상 매출 − 총경영비
- 심는 날 → 첫 수확 · 마지막 수확: 농사로 재배력 (crop_catalog.Cropping.schedule)
- 판매량 = 10a당 수량(조사 최근 3개 해 평균) × 면적(평 ÷ 302.5). 조사 수량이 이미 판 주산물이라 상품화율을 따로 곱하지 않음
- 예상 매출 = Σ(주마다 판매량 × 그날 농가 수취가) — 수확 기간을 7일씩 나눠 출하 비중(ship_weight)만큼 판다
  농가 수취가 = 전국 도매 예측가(DB price_forecast_daily, 없는 날은 평년) × farm_ratio (crop_prices.py) · 쌀·콩은 조사 수취가격
- 팔 시장: 토지 위치(시·도) 안 공영 도매시장 중 순이익이 가장 큰 곳. 시장 값 = 전국 × 그 시장 계수(DB market_factor, 달마다)
  (11/4 팀 결정: 수확한 지역 안의 도매시장에서 판다고 가정, 운송비·유통 마진은 계산하지 않음. 시장이 없는 시·도는 전국 평균)
- 총경영비 = 10a당 경영비(조사 평균, 토지임차료 뺌) × 면적 + 사용자가 넣은 임대료
- 순이익 범위 = 예측 하한·상한으로 판 매출 − 경영비
- 기존 작물(토지마다) → 흙 pH 어림. 후보 작물 최고값보다 0.5 이상 높으면 순이익과 상관없이 맨 아래로 (soil_ph.py)
- 한 작물에 작형이 여럿이면 고른 날 심을 수 있는 작형 중 순이익이 가장 큰 것 하나만 결과에 넣음
"""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

from app.core.crop_catalog import CROPS, LAND_TYPES, Crop, Cropping, ship_weight
from app.core.markets import NATIONAL, markets_in_sido
from app.core.soil_ph import SoilPh, ph_check, soil_ph_from_prev
from app.services import crop_prices
from app.services.crop_prices import Price

PYEONG_PER_10A = 302.5
WEEKS_AHEAD = 53  # 심는 날 비교 범위: 앞으로 1년(주 단위)
TIE_PCT = 0.5     # 마진률이 이만큼 안쪽으로 비슷하면 더 가까운 날을 고른다
TOP_N = 3         # 작물 정보 탭 "추천 상위" 기준
OFF_SEASON_REF = 0.5  # 매출의 절반 넘게가 출하철 밖(참고값) 날이면 화면에 '참고용'


@dataclass
class Rent:
    land: float = 0.0     # 만원
    machine: float = 0.0  # 만원


@dataclass(frozen=True)
class Week:
    day: date
    t: float              # 판매량 (톤)
    price: Price          # 그날 농가 수취가 (전국)


@dataclass
class Option:
    crop: Crop
    cropping: Cropping
    plant: date
    harvest_start: date
    harvest_end: date
    area_pyeong: float
    total_t: float
    weeks: list[Week]
    base_cost: float
    land_rent: float
    machine_rent: float
    today: date
    market: str = NATIONAL
    prev_crop: str | None = None
    soil_ph: float | None = None
    ph: tuple[str, SoilPh | None, float] | None = None
    _rev: dict[str, tuple[float, float, float]] = field(default_factory=dict, repr=False)

    # ── 매출 (시장마다 한 번 계산해 기억) ──
    def _revenue(self, market: str) -> tuple[float, float, float]:
        if market not in self._rev:
            r = lo = hi = 0.0
            for w in self.weeks:
                f = crop_prices.market_factor(self.crop, market, w.day.month)
                kg = w.t * 1000
                r += kg * w.price.wholesale * f
                lo += kg * w.price.low * f
                hi += kg * w.price.high * f
            self._rev[market] = (r, lo, hi)
        return self._rev[market]

    @property
    def sell_t(self) -> float:
        return self.total_t

    @property
    def revenue(self) -> float:
        return self._revenue(self.market)[0]

    @property
    def national_revenue(self) -> float:
        return self._revenue(NATIONAL)[0]

    @property
    def revenue_low(self) -> float:
        return self._revenue(self.market)[1]

    @property
    def revenue_high(self) -> float:
        return self._revenue(self.market)[2]

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
        """판 시장의 판매량 가중 평균 수취가 (원/kg)"""
        return self.revenue / (self.sell_t * 1000) if self.sell_t else 0.0

    @property
    def factor(self) -> float:
        return self.revenue / self.national_revenue if self.national_revenue else 1.0

    @property
    def error_pct(self) -> int:
        """예상 매출 범위의 반폭 (±%) — 예측 표 하한·상한으로 판 매출"""
        return round((self.revenue_high - self.revenue_low) / 2 / self.revenue * 100) if self.revenue else 0

    def share(self, pred) -> float:
        """매출 가운데 조건(pred(week))에 맞는 주의 몫 (전국 기준)"""
        tot = sum(w.t * w.price.wholesale for w in self.weeks)
        return sum(w.t * w.price.wholesale for w in self.weeks if pred(w)) / tot if tot else 0.0

    @property
    def basis(self) -> dict[str, float]:
        """가격 출처별 매출 몫: forecast(DB 예측) · normal(평년) · survey(조사 수취가)"""
        return {b: round(self.share(lambda w, b=b: w.price.basis == b), 3) for b in ("forecast", "normal", "survey") if self.share(lambda w, b=b: w.price.basis == b) > 0}

    @property
    def reference(self) -> str | None:
        """baseline: 매출 절반 넘게가 출하철 밖(채점해 본 적 없는 달) 예측 → 화면 '참고용' · far: 예측(1년) 밖이라 평년 가격이 절반 넘음"""
        if self.share(lambda w: w.price.off_season) > OFF_SEASON_REF:
            return "baseline"
        if self.share(lambda w: w.price.basis == "normal") > 0.5:
            return "far"
        return None

    @property
    def months_ahead(self) -> float:
        return (self.harvest_start - self.today).days / 30.44

    @property
    def shipments(self) -> list[tuple[str, float, float]]:
        """(YYYY-MM, 톤, 판 시장 매출) — 달마다"""
        out: dict[str, list[float]] = {}
        for w in self.weeks:
            m = out.setdefault(w.day.strftime("%Y-%m"), [0.0, 0.0])
            m[0] += w.t
            m[1] += w.t * 1000 * w.price.wholesale * crop_prices.market_factor(self.crop, self.market, w.day.month)
        return [(k, v[0], v[1]) for k, v in out.items()]

    @property
    def demoted(self) -> bool:
        return bool(self.ph and self.ph[0] == "lower")

    def at(self, market: str) -> "Option":
        """같은 계획을 다른 도매시장에 팔았을 때"""
        return replace(self, market=market, _rev=self._rev)


def harvest_weeks(c: Cropping, h0: date, h1: date) -> list[tuple[date, float]]:
    """(날, 출하 비중) — 7일 간격, 마지막 수확날 포함"""
    days, d = [], h0
    while d < h1:
        days.append(d)
        d += timedelta(days=7)
    days.append(h1)
    n = len(days)
    ws = [ship_weight(i / (n - 1) if n > 1 else 0, c.multi_harvest) for i in range(n)]
    s = sum(ws)
    return [(d, w / s) for d, w in zip(days, ws)]


def evaluate(crop: Crop, c: Cropping, plant: date, area_pyeong: float, today: date, rent: Rent | None = None, market: str | None = None) -> Option | None:
    """그날 심었을 때의 계획. 가격을 하나도 못 구하면 None"""
    rent = rent or Rent()
    h0, h1 = c.schedule(plant)
    a10 = area_pyeong / PYEONG_PER_10A
    total_t = c.yield_t_per_10a * a10
    weeks = []
    for d, w in harvest_weeks(c, h0, h1):
        p = crop_prices.farm_price(crop, c, d, today)
        if p is not None:
            weeks.append(Week(d, total_t * w, p))
    if not weeks:
        return None
    got = sum(w.t for w in weeks)
    if got < total_t:  # 가격이 없는 주가 있으면 판매량을 남은 주에 나눔
        weeks = [Week(w.day, w.t * total_t / got, w.price) for w in weeks]
    o = Option(crop=crop, cropping=c, plant=plant, harvest_start=h0, harvest_end=h1, area_pyeong=area_pyeong, total_t=total_t, weeks=weeks,
               base_cost=c.cost_per_10a * a10, land_rent=rent.land * 10_000, machine_rent=rent.machine * 10_000, today=today)
    return o.at(market) if market else o


def sido_markets(region: str, crop: Crop | None = None) -> tuple[list[str], bool]:
    """(그 시·도 안 시장 코드들, 시장이 없어 전국 평균을 쓰는지) — 다른 지역 시장은 섞지 않는다.
    쌀·콩(조사 수취가, 도매시장 값이 없음)은 시장 비교를 하지 않고 전국 평균"""
    if crop is not None and crop.price_source == "survey":
        return [NATIONAL], True
    here = [m.code for m in markets_in_sido(region)]
    return (here, False) if here else ([NATIONAL], True)


def compare_markets(o: Option, region: str) -> list[Option]:
    codes, _ = sido_markets(region, o.crop)
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


def croppings_on(crop: Crop, d: date, lands: dict[str, float]) -> list[Cropping]:
    return [c for c in crop.croppings if lands.get(c.land, 0) > 0 and c.in_window(d)]


def next_window(crop: Crop, after: date, lands: dict[str, float] | None = None) -> tuple[date, Cropping] | None:
    for k in range(1, 370):
        d = after + timedelta(days=k)
        for c in crop.croppings:
            if (lands is None or lands.get(c.land, 0) > 0) and c.in_window(d):
                return d, c
    return None


def best_on(crop: Crop, d: date, lands: dict[str, float], rents: dict[str, Rent], today: date, region: str, market: str | None) -> Option | None:
    """그날 그 작물을 심을 수 있는 작형(토지) 가운데 순이익이 가장 큰 계획"""
    best = None
    for c in croppings_on(crop, d, lands):
        o = evaluate(crop, c, d, lands[c.land], today, rents.get(c.land))
        if o is None:
            continue
        o = at_best_market(o, region, market)
        if best is None or o.margin > best.margin:
            best = o
    return best


def recommend_crops(
    lands: dict[str, float], rents: dict[str, Rent], start: date, today: date, region: str,
    market: str | None = None, prevs: dict[str, str | None] | None = None,
) -> tuple[list[Option], list[tuple[Crop, str, tuple[date, Cropping] | None]]]:
    """토지 종류별 평수·임대료·기존 작물 → (심을 수 있는 작물 순서대로, 지금 못 심는 작물과 이유)"""
    prevs = prevs or {}
    ok, off = [], []
    for crop in CROPS.values():
        if not any(lands.get(t, 0) > 0 for t in crop.land_types):
            continue
        if crop.perennial_note:
            off.append((crop, crop.perennial_note, None))
            continue
        o = best_on(crop, start, lands, rents, today, region, market)
        if o:
            ok.append(apply_soil(o, prevs.get(o.cropping.land)))
        else:
            off.append((crop, "심는 시기가 아니에요", next_window(crop, start, lands)))
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
        lands_txt = "·".join(LAND_TYPES[t] for t in crop.land_types)
        if crop.code in rank:
            i, o = rank[crop.code]
            if o.demoted:
                kind, p, gap = o.ph
                out.append((crop, "ph", f"심을 수는 있지만 {LAND_TYPES[o.cropping.land]} 토지 흙(기존 작물 {o.prev_crop} 기준 pH 약 {o.soil_ph})이 "
                                       f"알맞은 pH {p.min}~{p.max}보다 {gap} 높아서 맨 아래({i + 1}위)로 내렸어요."))
            elif i >= TOP_N:
                out.append((crop, "low", f"심을 수는 있지만 예상 순수익이 {round(o.margin / 1e4):,}만원(마진율 {round(o.margin_rate)}%)으로, "
                                        f"추천 상위({TOP_N}위 안)에 들지 못했어요. ({len(ok)}개 중 {i + 1}위)"))
            continue
        if crop.perennial_note:
            out.append((crop, "perennial", f"여러 해 기르는 나무라 날짜별 추천을 하지 않아요. {crop.perennial_note}"))
        elif not any(t in owned for t in crop.land_types):
            out.append((crop, "land", f"{lands_txt} 토지에서만 재배할 수 있어요. 고른 토지: {owned_txt}"))
        else:
            mine = [c for c in crop.croppings if c.land in owned]
            ws = ", ".join(f"{c.name} {_ten_day(c.plant_from)}~{_ten_day(c.plant_to)}" for c in mine)
            nxt = next_window(crop, start, lands)
            tail = f" 다음 심는 때: {nxt[0].month}/{nxt[0].day}부터({nxt[1].name})" if nxt else ""
            out.append((crop, "season", f"고른 날({start.month}/{start.day})은 심는 시기가 아니에요. 심는 때: {ws}.{tail}"))
    return out


def better(a: Option | None, b: Option, metric: str = "rate") -> Option:
    if a is None:
        return b
    va, vb = (a.margin_rate, b.margin_rate) if metric == "rate" else (a.margin, b.margin)
    tol = TIE_PCT if metric == "rate" else max(1.0, abs(va) * 0.01)
    return b if vb > va + tol else a


def planting_dates(crop: Crop, area_pyeong: float, today: date, rent: Rent | None = None, region: str = "서울", market: str | None = None,
                   land: str | None = None) -> tuple[list[tuple[date, Option | None]], Option | None, list[Option]]:
    """앞으로 1년, 주 단위로 심는 날별 결과 → (날짜별 결과, 마진률 최고, 작형별 최고 TOP). 화면에서는 안 쓰지만 API 는 남겨 둠"""
    lands = {land or t: area_pyeong for t in ([land] if land else crop.land_types)}
    rents = {t: rent or Rent() for t in lands}
    points = []
    for k in range(WEEKS_AHEAD):
        d = today + timedelta(days=7 * k)
        points.append((d, best_on(crop, d, lands, rents, today, region, market)))
    best = None
    per_cropping: dict[str, Option | None] = {}
    for _, o in points:
        if o is None:
            continue
        best = better(best, o)
        per_cropping[o.cropping.name] = better(per_cropping.get(o.cropping.name), o)
    top = sorted((o for o in per_cropping.values() if o), key=lambda o: o.margin_rate, reverse=True)
    return points, best, top


def price_on(crop: Crop, d: date, today: date) -> Price | None:
    """그날 전국 도매가 (작물 정보 그래프용): 예측 → 평년. 쌀·콩은 조사 수취가"""
    if crop.price_source == "survey":
        p = float(crop.survey_price or 0)
        return Price(p, p, p, "survey") if p else None
    return crop_prices.wholesale(crop, d, today)


__all__ = ["Option", "Rent", "TOP_N", "at_best_market", "compare_markets", "evaluate", "excluded", "planting_dates", "price_on",
           "recommend_crops", "sido_markets"]
