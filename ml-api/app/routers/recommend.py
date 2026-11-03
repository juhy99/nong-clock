from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.core.config import MODEL_VERSION
from app.core.crop_calendar import CROPS, LAND_TYPES, Crop
from app.schemas.recommend import (
    CropOut,
    Option,
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


def _option(o: recommender.Option, area: float) -> Option:
    c = o.cropping
    return Option(
        crop=o.crop.code, crop_name=o.crop.name, emoji=o.crop.emoji, land_type=o.crop.land_type, area_pyeong=area,
        cropping=c.name, plant_date=o.plant, harvest_start=o.harvest_start, harvest_end=o.harvest_end,
        price_per_kg=round(o.price), error_pct=recommender.error_pct(o.months_ahead), yield_t=round(o.yield_t, 2),
        revenue=round(o.revenue), cost=round(o.cost), margin=round(o.margin), margin_rate=round(o.margin_rate, 1),
        margin_per_pyeong=round(o.margin / area), yield_t_per_10a=c.yield_t_per_10a, cost_per_10a=round(c.cost_manwon_per_10a * 10_000),
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
    for land in req.lands:
        lands[land.type] = lands.get(land.type, 0) + land.area_pyeong
    ok, off = recommender.recommend_crops(lands, req.start_date, today)
    return RecommendCropsResponse(
        start_date=req.start_date,
        results=[_option(o, lands[o.crop.land_type]) for o in ok],
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
    points, best, top = recommender.planting_dates(crop, req.area_pyeong, date.today())
    return PlantingDatesResponse(
        crop=_crop_out(crop),
        best=_option(best, req.area_pyeong) if best else None,
        top=[_option(o, req.area_pyeong) for o in top[:3]],
        points=[PlantingPoint(plant_date=d, option=_option(o, req.area_pyeong) if o else None) for d, o in points],
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
