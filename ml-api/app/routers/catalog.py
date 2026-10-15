from fastapi import APIRouter

from app.core.catalog import ITEMS, REGIONS
from app.schemas.catalog import ItemOut, RegionOut

router = APIRouter(tags=["catalog"])


@router.get("/items", response_model=list[ItemOut], summary="예측 가능한 품목 목록")
def list_items() -> list[ItemOut]:
    return [ItemOut(code=i.code, name=i.name, unit=i.unit, category=i.category) for i in ITEMS.values()]


@router.get("/regions", response_model=list[RegionOut], summary="재배 지역 목록")
def list_regions() -> list[RegionOut]:
    return [RegionOut(code=code, name=name) for code, name in REGIONS.items()]
