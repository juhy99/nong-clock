from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.core.config import MODEL_VERSION
from app.core.crop_calendar import CROPS, LAND_TYPES, Crop
from app.core import accuracy
from app.core.markets import market_name
from app.core.soil_ph import ph_of
from app.schemas.recommend import (
    CroppingInfo,
    CropInfoResponse,
    CropOut,
    Excluded,
    PhInfo,
    SoilPhOut,
    MarketRef,
    MarketResult,
    Option,
    Per10a,
    RdaRef,
    Shipment,
    PlantingDatesRequest,
    PlantingDatesResponse,
    PlantingPoint,
    PricePathPoint,
    PricePathResponse,
    RecommendCropsRequest,
    RecommendCropsResponse,
    Unavailable,
)
from app.services import recommender

router = APIRouter(prefix="/recommend", tags=["recommend"])

START_WINDOW_DAYS = 365  # 농사 시작 날짜는 오늘부터 1년 안 (11-11, 화면에서 정확한 날짜를 받음. 예전 30일)
VERSION = f"{MODEL_VERSION}+crop-calendar-sample"


def _crop_out(c: Crop) -> CropOut:
    return CropOut(code=c.code, name=c.name, emoji=c.emoji, land_type=c.land_type, land_type_name=LAND_TYPES[c.land_type], perennial=bool(c.perennial_note))


def _market_ref(code: str) -> MarketRef:
    return MarketRef(code=code, name=market_name(code))


def _compare(o: recommender.Option, region: str) -> list[MarketResult]:
    xs = recommender.compare_markets(o, region)
    best = max(xs, key=lambda x: x.margin).market
    return [
        MarketResult(code=x.market, name=market_name(x.market), price_per_kg=round(x.price), revenue=round(x.revenue), margin=round(x.margin),
                     margin_rate=round(x.margin_rate, 1), factor=round(x.factor, 4), best=x.market == best)
        for x in xs
    ]


def _option(o: recommender.Option, region: str) -> Option:
    c, a10 = o.cropping, o.area_pyeong / recommender.PYEONG_PER_10A
    e = o.error_pct / 100
    r = o.crop.rda
    return Option(
        crop=o.crop.code, crop_name=o.crop.name, emoji=o.crop.emoji, land_type=o.crop.land_type, area_pyeong=o.area_pyeong,
        cropping=c.name, plant_date=o.plant, harvest_start=o.harvest_start, harvest_end=o.harvest_end,
        days_to_harvest=c.days_to_harvest, harvest_days=c.harvest_days, multi_harvest=c.multi_harvest,
        storage_days=c.storage_days, storage_end=o.harvest_end + timedelta(days=c.storage_days),
        region=region, market=_market_ref(o.market), factor=round(o.factor, 4), no_market=recommender.sido_markets(region)[1],
        prev_crop=o.prev_crop, soil_ph=o.soil_ph, demoted=o.demoted,
        ph=PhInfo(kind=o.ph[0], min=o.ph[1].min if o.ph[1] else None, max=o.ph[1].max if o.ph[1] else None, gap=o.ph[2]) if o.ph else None,
        price_per_kg=round(o.price), national_price_per_kg=round(o.price / o.factor), error_pct=o.error_pct, reference=o.reference,
        yield_t=round(o.total_t, 2), sellable_t=round(o.sell_t, 2), marketable_rate=o.crop.marketable,
        revenue=round(o.revenue), base_cost=round(o.base_cost), land_rent=round(o.land_rent), machine_rent=round(o.machine_rent),
        cost=round(o.cost), margin=round(o.margin), margin_rate=round(o.margin_rate, 1), margin_per_pyeong=round(o.margin / o.area_pyeong),
        margin_low=round(o.revenue * (1 - e) - o.cost), margin_high=round(o.revenue * (1 + e) - o.cost),
        national_margin=round(o.national_revenue - o.cost),
        yield_t_per_10a=c.yield_t_per_10a, cost_per_10a=round(c.cost_manwon_per_10a * 10_000), source=c.source,
        rda=RdaRef(row=r.row, revenue=r.revenue * 1000, cost=r.cost * 1000, income=r.income * 1000, kg=r.kg, price=r.price) if r else None,
        per_10a=Per10a(revenue=round(o.revenue / a10), cost=round(o.base_cost / a10), income=round((o.revenue - o.base_cost) / a10)),
        shipments=[Shipment(month=m, t=round(t, 2), price_per_kg=round(won * o.factor / (t * 1000)), revenue=round(won * o.factor)) for m, t, won in o.shipments],
        market_compare=_compare(o, region),
    )


@router.get("/crops", response_model=list[CropOut], summary="추천에 쓰는 작물 목록")
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
    return RecommendCropsResponse(
        start_date=req.start_date, region=req.region, markets=[_market_ref(c) for c in codes], no_market=none,
        results=[_option(o, req.region) for o in ok],
        excluded=[Excluded(crop=c.code, crop_name=c.name, emoji=c.emoji, land_type=c.land_type, kind=k, reason=why)
                  for c, k, why in recommender.excluded(ok, lands, req.start_date)],
        unavailable=[
            Unavailable(crop=c.code, crop_name=c.name, emoji=c.emoji, land_type=c.land_type, reason=why,
                        next_plant_date=nxt[0] if nxt else None, next_cropping=nxt[1].name if nxt else None)
            for c, why, nxt in off
        ],
        model_version=VERSION,
    )


@router.post("/planting-dates", response_model=PlantingDatesResponse, summary="(화면에서는 안 씀) 작물로 가장 좋은 심는 날 고르기")
def planting_dates(req: PlantingDatesRequest) -> PlantingDatesResponse:
    crop = CROPS.get(req.crop)
    if crop is None:
        raise HTTPException(status_code=404, detail=f"unknown crop: {req.crop}")
    if crop.perennial_note:
        return PlantingDatesResponse(crop=_crop_out(crop), note=crop.perennial_note, best=None, top=[], points=[], model_version=VERSION)
    rent = recommender.Rent(req.land_rent, req.machine_rent)
    points, best, top = recommender.planting_dates(crop, req.area_pyeong, date.today(), rent, req.region, req.market)
    return PlantingDatesResponse(
        crop=_crop_out(crop),
        best=_option(best, req.region) if best else None,
        top=[_option(o, req.region) for o in top[:3]],
        points=[PlantingPoint(plant_date=d, option=_option(o, req.region) if o else None) for d, o in points],
        model_version=VERSION,
    )


@router.get("/crops/{code}", response_model=CropInfoResponse, summary="작물 정보: 작형별 심는 기간·일수·10a당 수량·경영비·알맞은 pH (작물 정보 탭)")
def crop_info(code: str) -> CropInfoResponse:
    crop = CROPS.get(code)
    if crop is None:
        raise HTTPException(status_code=404, detail=f"unknown crop: {code}")
    r, p = crop.rda, ph_of(code)
    return CropInfoResponse(
        crop=_crop_out(crop), note=crop.perennial_note, marketable_rate=crop.marketable,
        rda=RdaRef(row=r.row, revenue=r.revenue * 1000, cost=r.cost * 1000, income=r.income * 1000, kg=r.kg, price=r.price) if r else None,
        soil_ph=SoilPhOut(name=p.name, min=p.min, max=p.max, memo=p.memo) if p else None,
        croppings=[
            CroppingInfo(name=c.name, plant_from=c.plant_from, plant_to=c.plant_to, days_to_harvest=c.days_to_harvest, harvest_days=c.harvest_days,
                         storage_days=c.storage_days, multi_harvest=c.multi_harvest, yield_t_per_10a=c.yield_t_per_10a,
                         cost_per_10a=round(c.cost_manwon_per_10a * 10_000), source=c.source)
            for c in crop.croppings
        ],
        model_version=VERSION,
    )


@router.get("/crops/{code}/prices", response_model=PricePathResponse, summary="작물의 앞으로 12개월 예상 도매가 (상세 그래프, 주 단위 53점)")
def price_path(code: str) -> PricePathResponse:
    crop = CROPS.get(code)
    if crop is None:
        raise HTTPException(status_code=404, detail=f"unknown crop: {code}")
    if crop.perennial_note:
        return PricePathResponse(crop=_crop_out(crop), points=[], model_version=VERSION)
    today = date.today()
    pts = []
    for k in range(53):  # 오늘 + 52주 = 12개월 (11-11, 예전 13개월 57점)
        d = today + timedelta(days=7 * k)
        v = recommender.price_on(crop, d, today)
        e = accuracy.error_pct(code, max(1, (d - today).days)) / 100  # 모델 검증 오차(WAPE)
        pts.append(PricePathPoint(date=d, price=round(v), lower=round(v * (1 - e)), upper=round(v * (1 + e))))
    return PricePathResponse(crop=_crop_out(crop), points=pts, model_version=VERSION)
