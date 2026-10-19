import os

APP_NAME = "nong-clock ml-api"
MODEL_VERSION = os.getenv("MODEL_VERSION", "dummy-0.1")

# 지역별 예측 사용 여부. 기본은 전국만.
ENABLE_REGIONAL_FORECAST = os.getenv("ENABLE_REGIONAL_FORECAST", "false").lower() in ("1", "true", "yes")

# 쉼표로 구분. Spring을 거쳐 호출하면 비워둬도 되지만, 프론트 로컬 개발 편의를 위해 기본값을 둔다.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",")
    if origin.strip()
]
