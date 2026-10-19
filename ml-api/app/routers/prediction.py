from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.catalog import HORIZONS, ITEMS, NATIONAL, REGIONS
from app.schemas.prediction import PredictRequest, PredictResponse, TopMover
from app.services.predictor import Predictor, get_predictor

router = APIRouter(prefix="/predict", tags=["prediction"])

PredictorDep = Annotated[Predictor, Depends(get_predictor)]


@router.post("", response_model=PredictResponse, summary="품목·지역별 가격 예측 (AI 가격예측 화면)")
def predict(req: PredictRequest, predictor: PredictorDep) -> PredictResponse:
    if req.item not in ITEMS:
        raise HTTPException(status_code=404, detail=f"unknown item: {req.item}")
    if req.region not in REGIONS:
        raise HTTPException(status_code=404, detail=f"unknown region: {req.region}")
    return predictor.predict(req.item, req.region, req.horizon, date.today())


@router.get("/top-movers", response_model=list[TopMover], summary="급등락 예상 품목 (홈 AI 추천 카드)")
def top_movers(
    predictor: PredictorDep,
    # 쿼리 문자열("7")은 Literal[7, 14, 30] 검사를 통과하지 못해서 int 로 받은 뒤 직접 확인한다.
    horizon: int = 7,
    limit: Annotated[int, Query(ge=1, le=len(ITEMS))] = 4,
    region: str = NATIONAL,
) -> list[TopMover]:
    if horizon not in HORIZONS:
        raise HTTPException(status_code=422, detail=f"horizon must be one of {list(HORIZONS)}")
    if region not in REGIONS:
        raise HTTPException(status_code=404, detail=f"unknown region: {region}")
    today = date.today()
    movers = []
    for code in ITEMS:
        p = predictor.predict(code, region, horizon, today)
        movers.append(
            TopMover(
                item=p.item,
                item_name=p.item_name,
                unit=p.unit,
                predicted_price=p.predicted_price,
                change_pct=p.change_pct,
                confidence=p.confidence,
            )
        )
    movers.sort(key=lambda m: abs(m.change_pct), reverse=True)
    return movers[:limit]
