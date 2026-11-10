from fastapi import APIRouter

from app.core.catalog import HORIZONS, PREDICT_ITEMS, REGIONS
from app.core.markets import MARKETS
from app.schemas.catalog import HorizonOut, ItemOut, MarketOut, RegionOut

router = APIRouter(tags=["catalog"])


@router.get("/items", response_model=list[ItemOut], summary="예측 품목 목록 (50개, 물량 순위 순 — shared/items50.json)")
def list_items() -> list[ItemOut]:
    return [ItemOut(code=i.code, name=i.name, code4=i.code4, unit=i.unit, category=i.category, emoji=i.emoji) for i in PREDICT_ITEMS.values()]


@router.get("/markets", response_model=list[MarketOut], summary="공영 도매시장 32곳 (가격 예측·작물 추천의 시장 코드)")
def list_markets() -> list[MarketOut]:
    return [MarketOut(code=m.code, name=m.name, sido=m.sido, sigungu=m.sigungu, lat=m.lat, lon=m.lon) for m in MARKETS.values()]


@router.get("/regions", response_model=list[RegionOut], summary="(예전 방식) 재배 지역 목록 — 가격은 /markets 의 도매시장별로 예측", deprecated=True)
def list_regions() -> list[RegionOut]:
    return [RegionOut(code=code, name=name) for code, name in REGIONS.items()]


@router.get("/horizons", response_model=list[HorizonOut], summary="예측 기간 빠른 선택 (1주~1년)")
def list_horizons() -> list[HorizonOut]:
    return [HorizonOut(days=days, label=label) for days, label in HORIZONS.items()]
