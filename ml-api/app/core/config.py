import os

APP_NAME = "nong-clock ml-api"
# 예측기: dummy(가짜, 기본) · db(DB 의 실제 시세 + price_forecast_daily 일 단위 예측, 11-13). db 면 PGHOST 등 DB 접속 정보도 필요
PREDICTOR = os.getenv("PREDICTOR", "dummy").strip().lower()

# 관리자 '서버 상태'에 보이는 모델 이름. 11-17: 실제 예측(db)인데 .env 가 예전 값 dummy-0.1 이면 최종 모델 이름으로 (가짜 모델처럼 보이던 문제)
FINAL_MODEL = "final-1117 (u7d+원인 1~14거래일 · v4 월 · 달 이음)"
MODEL_VERSION = os.getenv("MODEL_VERSION", "").strip()
if not MODEL_VERSION or (PREDICTOR == "db" and MODEL_VERSION.startswith("dummy")):
    MODEL_VERSION = FINAL_MODEL if PREDICTOR == "db" else "dummy-0.1"

# 지역별 예측 사용 여부. 기본은 전국만.
ENABLE_REGIONAL_FORECAST = os.getenv("ENABLE_REGIONAL_FORECAST", "false").lower() in ("1", "true", "yes")

# 쉼표로 구분. Spring을 거쳐 호출하면 비워둬도 되지만, 프론트 로컬 개발 편의를 위해 기본값을 둔다.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",")
    if origin.strip()
]
