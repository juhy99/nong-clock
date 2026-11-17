"""로그인 없이 볼 수 있는 미리보기 (11-17).

서버(nginx)는 /ml/predict · /ml/recommend 를 회원 로그인이 있어야 통과시킨다 (frontend/nginx.conf).
홈·뉴스 화면의 미리보기는 로그인 전에도 보여야 해서, 정해진 조건으로만 답하는 이 주소를 따로 둔다:
  GET /public/predict?item=&horizon=7|28   전국 평균만 · 오늘 기준만 · 7일 또는 4주
  GET /public/recommend?region=&type=      1,200평 · 오늘 심는 경우 · 순수익 위 3개만
시장·품종·날짜·기간(365일)·내 땅 조건을 고르는 본 기능은 /predict · /recommend (회원만).
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.routers import prediction, recommend
from app.routers.prediction import PredictorDep
from app.schemas.prediction import PredictRequest, PredictResponse
from app.schemas.recommend import Land, LandType, RecommendCropsRequest, RecommendCropsResponse, Sido

router = APIRouter(prefix="/public", tags=["public"])

PREVIEW_HISTORY = {7: 14, 28: 49}   # 예측 기간 → 앞쪽 실제 시세 일수 (뉴스 옆 카드 · 홈 그래프)
PREVIEW_AREA = 1200
PREVIEW_TOP = 3


@router.get("/predict", response_model=PredictResponse, summary="미리보기: 품목의 전국 평균 7일·4주 예측 (홈 · 뉴스)")
def preview_predict(item: str, predictor: PredictorDep, horizon: int = 28) -> PredictResponse:
    if horizon not in PREVIEW_HISTORY:
        raise HTTPException(status_code=422, detail="미리보기는 7일 · 28일만 볼 수 있어요 (다른 기간은 로그인 후 AI 가격 예측에서)")
    return prediction.predict(PredictRequest(item=item, horizon=horizon, history_days=PREVIEW_HISTORY[horizon]), predictor)


@router.get("/recommend", response_model=RecommendCropsResponse, summary="미리보기: 오늘 1,200평에 심으면 순수익 위 3개 (홈)")
def preview_recommend(region: Annotated[Sido, Query()] = "경기", type: Annotated[LandType, Query()] = "open") -> RecommendCropsResponse:
    res = recommend.recommend_crops(RecommendCropsRequest(region=region, lands=[Land(type=type, area_pyeong=PREVIEW_AREA)], start_date=date.today()))
    res.results, res.orchards, res.excluded, res.unavailable = res.results[:PREVIEW_TOP], res.orchards[:PREVIEW_TOP], [], []
    return res
