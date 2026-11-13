from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.core.crop_catalog import BUILT_AT, CROPS, LAND_TYPES, Crop, Survey
from app.core.markets import market_name
from app.core.soil_ph import ph_of
from app.schemas.recommend import (
    CroppingInfo,
    CropInfoResponse,
    CropOut,
    Excluded,
    MarketRef,
    MarketResult,
    Option,
    Per10a,
    PhInfo,
    PlantingDatesRequest,
    PlantingDatesResponse,
    PlantingPoint,
    PricePathPoint,
    PricePathResponse,
    RdaRef,
    RecommendCropsRequest,
    RecommendCropsResponse,
    Shipment,
    SoilPhOut,
    Unavailable,
)
from app.services import crop_prices, recommender

router = APIRouter(prefix="/recommend", tags=["recommend"])

START_WINDOW_DAYS = 365  # 농사 시작 날짜는 오늘부터 1년 안 (11-11)


def _version(base: date | None) -> str:
    """작물 표 만든 날 · 쓴 AI 예측 기준일 (예측을 못 쓰면 평년 가격)"""
    return f"작물표 {BUILT_AT} · " + (f"AI 예측 기준일 {base:%Y-%m-%d}" if base else "평년 가격")


def _crop_out(c: Crop) -> CropOut:
    return CropOut(code=c.code, name=c.name, emoji=c.emoji, land_type=c.land_type, land_type_name=LAND_TYPES[c.land_type],
                   land_types=list(c.land_types), perennial=bool(c.perennial_note))


def _market_ref(code: str) -> MarketRef:
    return MarketRef(code=code, name=market_name(code))


def _rda(s: Survey | None) -> RdaRef | None:
    if s is None:
        return None
    return RdaRef(row=s.row, source=s.source, years=list(s.years), revenue=s.revenue, cost=s.cost, income=s.income, kg=s.kg, price=s.price,
                  land_rent=s.land_rent)


def _compare(o: recommender.Option, region: str) -> list[MarketResult]:
    xs = recommender.compare_markets(o, region)
    best = max(xs, key=lambda x: x.margin).market
    return [
        MarketResult(code=x.market, name=market_name(x.market), price_per_kg=round(x.price), revenue=round(x.revenue), margin=round(x.margin),
                     margin_rate=round(x.margin_rate, 1), factor=round(x.factor, 4), best=x.market == best)
        for x in xs
    ]


def _option(o: recommender.Option, region: str, today: date) -> Option:
    c, a10 = o.cropping, o.area_pyeong / recommender.PYEONG_PER_10A
    nat = o.national_revenue
    return Option(
        crop=o.crop.code, crop_name=o.crop.name, emoji=o.crop.emoji, land_type=c.land, area_pyeong=o.area_pyeong,
        cropping=c.name, schedule_source=c.schedule_source, econ_source=c.econ_source,
        plant_date=o.plant, harvest_start=o.harvest_start, harvest_end=o.harvest_end,
        days_to_harvest=(o.harvest_start - o.plant).days, harvest_days=(o.harvest_end - o.harvest_start).days, multi_harvest=c.multi_harvest,
        storage_days=c.storage_days, storage_end=o.harvest_end + timedelta(days=c.storage_days),
        region=region, market=_market_ref(o.market), factor=round(o.factor, 4), no_market=recommender.sido_markets(region, o.crop)[1],
        prev_crop=o.prev_crop, soil_ph=o.soil_ph, demoted=o.demoted,
        ph=PhInfo(kind=o.ph[0], min=o.ph[1].min if o.ph[1] else None, max=o.ph[1].max if o.ph[1] else None, gap=o.ph[2]) if o.ph else None,
        price_per_kg=round(o.price), national_price_per_kg=round(nat / (o.sell_t * 1000)) if o.sell_t else 0,
        farm_ratio=c.farm_ratio if o.crop.price_source != "survey" else None, price_basis=o.basis,
        forecast_base_date=crop_prices.forecast_base(o.crop, today) if o.basis.get("forecast") else None,
        error_pct=o.error_pct, reference=o.reference,
        yield_t=round(o.total_t, 2), sellable_t=round(o.sell_t, 2), marketable_rate=1.0,
        revenue=round(o.revenue), base_cost=round(o.base_cost), land_rent=round(o.land_rent), machine_rent=round(o.machine_rent),
        cost=round(o.cost), margin=round(o.margin), margin_rate=round(o.margin_rate, 1), margin_per_pyeong=round(o.margin / o.area_pyeong),
        margin_low=round(o.revenue_low - o.cost), margin_high=round(o.revenue_high - o.cost), national_margin=round(nat - o.cost),
        yield_t_per_10a=c.yield_t_per_10a, cost_per_10a=c.cost_per_10a, source=c.source, rda=_rda(c.survey),
        per_10a=Per10a(revenue=round(o.revenue / a10), cost=round(o.base_cost / a10), income=round((o.revenue - o.base_cost) / a10)),
        shipments=[Shipment(month=m, t=round(t, 2), price_per_kg=round(won / (t * 1000)) if t else 0, revenue=round(won)) for m, t, won in o.shipments],
        market_compare=_compare(o, region),
    )


def _get(code: str) -> Crop:
    crop = CROPS.get(code)
    if crop is None:
        raise HTTPException(status_code=404, detail=f"unknown crop: {code}")
    return crop


@router.get("/crops", response_model=list[CropOut], summary="추천에 쓰는 작물 목록 (shared/crops.json, 34개)")
def list_crops() -> list[CropOut]:
    return [_crop_out(c) for c in CROPS.values()]


@router.post("/crops", response_model=RecommendCropsResponse, summary="내 땅으로 작물 고르기 (순이익 높은 순, 시·도 안 도매시장 비교, 기존 작물 pH 반영)")
def recommend_crops(req: RecommendCropsRequest) -> RecommendCropsResponse:
    today = date.today()
    if not today <= req.start_date <= today + timedelta(days=START_WINDOW_DAYS):
        raise HTTPException(status_code=422, detail=f"start_date 는 오늘부터 {START_WINDOW_DAYS}일 안이어야 해요")
    lands: dict[str, float] = {}
    rents: dict[str, recommender.Rent] = {}
    prevs: dict[str, str | None] = {}
    for land in req.lands:
        lands[land.type] = lands.get(land.type, 0) + land.area_pyeong
        r = rents.setdefault(land.type, recommender.Rent())
        r.land += land.land_rent
        r.machine += land.machine_rent
        prevs[land.type] = land.prev_crop or prevs.get(land.type)
    ok, off = recommender.recommend_crops(lands, rents, req.start_date, today, req.region, req.market, prevs)
    codes, none = recommender.sido_markets(req.region)
    bases = [b for b in (crop_prices.forecast_base(o.crop, today) for o in ok) if b]
    return RecommendCropsResponse(
        start_date=req.start_date, region=req.region, markets=[_market_ref(c) for c in codes], no_market=none,
        results=[_option(o, req.region, today) for o in ok],
        excluded=[Excluded(crop=c.code, crop_name=c.name, emoji=c.emoji, land_type=c.land_type, kind=k, reason=why)
                  for c, k, why in recommender.excluded(ok, lands, req.start_date)],
        unavailable=[
            Unavailable(crop=c.code, crop_name=c.name, emoji=c.emoji, land_type=c.land_type, reason=why,
                        next_plant_date=nxt[0] if nxt else None, next_cropping=nxt[1].name if nxt else None)
            for c, why, nxt in off
        ],
        model_version=_version(max(bases) if bases else None),
    )


@router.post("/planting-dates", response_model=PlantingDatesResponse, summary="(화면에서는 안 씀) 작물로 가장 좋은 심는 날 고르기")
def planting_dates(req: PlantingDatesRequest) -> PlantingDatesResponse:
    crop = _get(req.crop)
    today = date.today()
    if crop.perennial_note:
        return PlantingDatesResponse(crop=_crop_out(crop), note=crop.perennial_note, best=None, top=[], points=[], model_version=_version(None))
    if req.land and req.land not in crop.land_types:
        raise HTTPException(status_code=422, detail=f"{crop.name} 은(는) {LAND_TYPES[req.land]} 토지 작형이 없어요")
    rent = recommender.Rent(req.land_rent, req.machine_rent)
    points, best, top = recommender.planting_dates(crop, req.area_pyeong, today, rent, req.region, req.market, req.land)
    return PlantingDatesResponse(
        crop=_crop_out(crop),
        best=_option(best, req.region, today) if best else None,
        top=[_option(o, req.region, today) for o in top[:3]],
        points=[PlantingPoint(plant_date=d, option=_option(o, req.region, today) if o else None) for d, o in points],
        model_version=_version(crop_prices.forecast_base(crop, today)),
    )


@router.get("/crops/{code}", response_model=CropInfoResponse, summary="작물 정보: 작형별 심는 때·수확 때·10a당 수량·경영비·알맞은 pH (작물 정보 탭)")
def crop_info(code: str) -> CropInfoResponse:
    crop = _get(code)
    p = ph_of(code)
    return CropInfoResponse(
        crop=_crop_out(crop), note=crop.perennial_note, harvest_months=crop.harvest_months, price_source=crop.price_source,
        normal=dict(price=list(crop.normal_price), low=list(crop.normal_low), high=list(crop.normal_high)) if crop.normal_price else None,
        marketable_rate=1.0, rda=_rda(crop.survey),
        soil_ph=SoilPhOut(name=p.name, min=p.min, max=p.max, memo=p.memo) if p else None,
        croppings=[
            CroppingInfo(name=c.name, land=c.land, plant_from=c.plant_from, plant_to=c.plant_to, harvest_from=c.harvest_from, harvest_to=c.harvest_to,
                         days_to_harvest=c.days_to_harvest, harvest_days=c.harvest_days, storage_days=c.storage_days, multi_harvest=c.multi_harvest,
                         yield_t_per_10a=c.yield_t_per_10a, cost_per_10a=c.cost_per_10a, farm_ratio=c.farm_ratio, source=c.source,
                         schedule_source=c.schedule_source, econ_source=c.econ_source)
            for c in crop.croppings
        ],
        model_version=_version(None),
    )


@router.get("/crops/{code}/prices", response_model=PricePathResponse, summary="작물의 앞으로 12개월 예상 도매가 (상세 그래프, 주 단위 53점)")
def price_path(code: str) -> PricePathResponse:
    crop = _get(code)
    today = date.today()
    if crop.perennial_note and crop.price_source == "survey":
        return PricePathResponse(crop=_crop_out(crop), points=[], model_version=_version(None))
    pts = []
    for k in range(53):  # 오늘 + 52주 = 12개월
        d = today + timedelta(days=7 * k)
        v = recommender.price_on(crop, max(d, today + timedelta(days=1)), today)  # 오늘 점은 예측 첫날(내일) 값 — 예측 표는 기준일 다음 날부터
        if v is None:
            continue
        pts.append(PricePathPoint(date=d, price=round(v.wholesale), lower=round(v.low), upper=round(v.high), basis=v.basis, off_season=v.off_season))
    base = crop_prices.forecast_base(crop, today)
    return PricePathResponse(crop=_crop_out(crop), points=pts, forecast_base_date=base, model_version=_version(base))
