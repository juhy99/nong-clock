from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.core.config import MODEL_VERSION
from app.core.crop_calendar import CROPS, LAND_TYPES, Crop
from app.core.markets import MARKETS, markets_near
from app.schemas.recommend import (
    CropOut,
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

START_WINDOW_DAYS = 30  # 농사 시작 날짜는 오늘부터 30일 안
VERSION = f"{MODEL_VERSION}+crop-calendar-sample"


def _crop_out(c: Crop) -> CropOut:
    return CropOut(code=c.code, name=c.name, emoji=c.emoji, land_type=c.land_type, land_type_name=LAND_TYPES[c.land_type], perennial=bool(c.perennial_note))


def _market_ref(code: str, region: str) -> MarketRef:
    if code == "national":
        return MarketRef(code="national", name="전국 평균", km=None)
    km = next((k for m, k in markets_near(region) if m.code == code), None)
    return MarketRef(code=code, name=MARKETS[code].name, km=km)


def _option(o: recommender.Option, region: str) -> Option:
    c, a10 = o.cropping, o.area_pyeong / recommender.PYEONG_PER_10A
    e = o.error_pct / 100
    r = o.crop.rda
    return Option(
        crop=o.crop.code, crop_name=o.crop.name, emoji=o.crop.emoji, land_type=o.crop.land_type, area_pyeong=o.area_pyeong,
        cropping=c.name, plant_date=o.plant, harvest_start=o.harvest_start, harvest_end=o.harvest_end,
        days_to_harvest=c.days_to_harvest, harvest_days=c.harvest_days, multi_harvest=c.multi_harvest,
        storage_days=c.storage_days, storage_end=o.harvest_end + timedelta(days=c.storage_days),
        region=region, market=_market_ref(o.market, region), factor=round(o.factor, 4),
        price_per_kg=round(o.price), national_price_per_kg=round(o.price / o.factor), error_pct=o.error_pct,
        yield_t=round(o.total_t, 2), sellable_t=round(o.sell_t, 2), marketable_rate=o.crop.marketable,
        revenue=round(o.revenue), base_cost=round(o.base_cost), land_rent=round(o.land_rent), machine_rent=round(o.machine_rent),
        cost=round(o.cost), margin=round(o.margin), margin_rate=round(o.margin_rate, 1), margin_per_pyeong=round(o.margin / o.area_pyeong),
        margin_low=round(o.revenue * (1 - e) - o.cost), margin_high=round(o.revenue * (1 + e) - o.cost),
        national_margin=round(o.national_revenue - o.cost),
        yield_t_per_10a=c.yield_t_per_10a, cost_per_10a=round(c.cost_manwon_per_10a * 10_000), source=c.source,
        rda=RdaRef(row=r.row, revenue=r.revenue * 1000, cost=r.cost * 1000, income=r.income * 1000, kg=r.kg, price=r.price) if r else None,
        per_10a=Per10a(revenue=round(o.revenue / a10), cost=round(o.base_cost / a10), income=round((o.revenue - o.base_cost) / a10)),
        shipments=[Shipment(month=m, t=round(t, 2), price_per_kg=round(won * o.factor / (t * 1000)), revenue=round(won * o.factor)) for m, t, won in o.shipments],
        market_compare=[
            MarketResult(code=code, name=name, km=km, price_per_kg=round(x.price), revenue=round(x.revenue), margin=round(x.margin),
                         margin_rate=round(x.margin_rate, 1), factor=round(x.factor, 4))
            for code, name, km, x in recommender.compare_markets(o, region)
        ],
    )


@router.get("/crops", response_model=list[CropOut], summary="추천에 쓰는 작물 목록")
def list_crops() -> list[CropOut]:
    return [_crop_out(c) for c in CROPS.values()]


@router.post("/crops", response_model=RecommendCropsResponse, summary="내 땅으로 작물 고르기 (마진 높은 순)")
def recommend_crops(req: RecommendCropsRequest) -> RecommendCropsResponse:
    today = date.today()
    if not today <= req.start_date <= today + timedelta(days=START_WINDOW_DAYS):
        raise HTTPException(status_code=422, detail=f"start_date 는 오늘부터 {START_WINDOW_DAYS}일 안이어야 해요")
    lands: dict[str, float] = {}
    rents: dict[str, recommender.Rent] = {}
    for land in req.lands:
        lands[land.type] = lands.get(land.type, 0) + land.area_pyeong
        r = rents.setdefault(land.type, recommender.Rent())
        r.land += land.land_rent
        r.machine += land.machine_rent
    market = recommender.pick_market(req.region, req.market)
    ok, off = recommender.recommend_crops(lands, rents, req.start_date, today, market)
    return RecommendCropsResponse(
        start_date=req.start_date, region=req.region, market=_market_ref(market, req.region),
        results=[_option(o, req.region) for o in ok],
        unavailable=[
            Unavailable(crop=c.code, crop_name=c.name, emoji=c.emoji, land_type=c.land_type, reason=why,
                        next_plant_date=nxt[0] if nxt else None, next_cropping=nxt[1].name if nxt else None)
            for c, why, nxt in off
        ],
        model_version=VERSION,
    )


@router.post("/planting-dates", response_model=PlantingDatesResponse, summary="작물로 가장 좋은 심는 날 고르기")
def planting_dates(req: PlantingDatesRequest) -> PlantingDatesResponse:
    crop = CROPS.get(req.crop)
    if crop is None:
        raise HTTPException(status_code=404, detail=f"unknown crop: {req.crop}")
    if crop.perennial_note:
        return PlantingDatesResponse(crop=_crop_out(crop), note=crop.perennial_note, best=None, top=[], points=[], model_version=VERSION)
    market = recommender.pick_market(req.region, req.market)
    rent = recommender.Rent(req.land_rent, req.machine_rent)
    points, best, top = recommender.planting_dates(crop, req.area_pyeong, date.today(), rent, market)
    return PlantingDatesResponse(
        crop=_crop_out(crop),
        best=_option(best, req.region) if best else None,
        top=[_option(o, req.region) for o in top[:3]],
        points=[PlantingPoint(plant_date=d, option=_option(o, req.region) if o else None) for d, o in points],
        model_version=VERSION,
    )


@router.get("/crops/{code}/prices", response_model=PricePathResponse, summary="작물의 앞으로 13개월 예상 도매가 (상세 그래프)")
def price_path(code: str) -> PricePathResponse:
    crop = CROPS.get(code)
    if crop is None:
        raise HTTPException(status_code=404, detail=f"unknown crop: {code}")
    if crop.perennial_note:
        return PricePathResponse(crop=_crop_out(crop), points=[], model_version=VERSION)
    today = date.today()
    pts = []
    for k in range(57):
        d = today + timedelta(days=7 * k)
        v = recommender.price_on(crop, d, today)
        e = recommender.error_pct((d - today).days / 30.44) / 100 * 0.7  # 80% 범위로 줄여 표시
        pts.append(PricePathPoint(date=d, price=round(v), lower=round(v * (1 - e)), upper=round(v * (1 + e))))
    return PricePathResponse(crop=_crop_out(crop), points=pts, model_version=VERSION)
