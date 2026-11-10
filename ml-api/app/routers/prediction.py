from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.catalog import BASE_DATE_BACK_DAYS, MAX_HORIZON, NATIONAL, PREDICT_ITEMS, REGIONS
from app.core.markets import MARKETS
from app.schemas.prediction import PredictRequest, PredictResponse, TopMover
from app.services.predictor import Predictor, get_predictor

router = APIRouter(prefix="/predict", tags=["prediction"])

PredictorDep = Annotated[Predictor, Depends(get_predictor)]


def _check_market(market: str) -> None:
    if market != NATIONAL and market not in MARKETS:
        raise HTTPException(status_code=404, detail=f"unknown market: {market}")


@router.post("", response_model=PredictResponse, summary="품목·도매시장별 가격 예측, 최대 365일 (AI 가격예측 화면)")
def predict(req: PredictRequest, predictor: PredictorDep) -> PredictResponse:
    if req.item not in PREDICT_ITEMS:
        raise HTTPException(status_code=404, detail=f"unknown item: {req.item} (예측 품목은 GET /items 의 50개)")
    if req.region not in REGIONS:
        raise HTTPException(status_code=404, detail=f"unknown region: {req.region}")
    _check_market(req.market)
    today = date.today()
    base = req.base_date or today
    if not today - timedelta(days=BASE_DATE_BACK_DAYS) <= base <= today:
        raise HTTPException(status_code=422, detail=f"base_date 는 오늘부터 {BASE_DATE_BACK_DAYS}일 전까지만 고를 수 있어요")
    res = predictor.predict(req.item, req.market, req.horizon, base, req.history_days, req.last_year)
    res.region = req.region  # (예전 방식) 지역은 그대로 돌려줌
    return res


@router.get("/top-movers", response_model=list[TopMover], summary="급등락 예상 품목 (홈 AI 추천 카드)")
def top_movers(
    predictor: PredictorDep,
    horizon: Annotated[int, Query(ge=1, le=MAX_HORIZON)] = 7,
    limit: Annotated[int, Query(ge=1, le=len(PREDICT_ITEMS))] = 4,
    market: str = NATIONAL,
) -> list[TopMover]:
    _check_market(market)
    today = date.today()
    movers = []
    for code in PREDICT_ITEMS:
        p = predictor.predict(code, market, horizon, today)
        movers.append(
            TopMover(
                item=p.item,
                item_name=p.item_name,
                unit=p.unit,
                predicted_price=p.predicted_price,
                change_pct=p.change_pct,
                confidence=p.confidence,
                error_pct=p.error_pct,
                reference=p.reference,
            )
        )
    movers.sort(key=lambda m: abs(m.change_pct), reverse=True)
    return movers[:limit]
