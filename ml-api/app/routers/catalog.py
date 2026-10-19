from fastapi import APIRouter

from app.core.catalog import HORIZONS, ITEMS, REGIONS
from app.schemas.catalog import HorizonOut, ItemOut, RegionOut

router = APIRouter(tags=["catalog"])


@router.get("/items", response_model=list[ItemOut], summary="예측 가능한 품목 목록")
def list_items() -> list[ItemOut]:
    return [ItemOut(code=i.code, name=i.name, unit=i.unit, category=i.category, emoji=i.emoji) for i in ITEMS.values()]


@router.get("/regions", response_model=list[RegionOut], summary="재배 지역 목록")
def list_regions() -> list[RegionOut]:
    return [RegionOut(code=code, name=name) for code, name in REGIONS.items()]


@router.get("/horizons", response_model=list[HorizonOut], summary="예측 기간 목록")
def list_horizons() -> list[HorizonOut]:
    return [HorizonOut(days=days, label=label) for days, label in HORIZONS.items()]
