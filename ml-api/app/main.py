from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import APP_NAME, CORS_ORIGINS, MODEL_VERSION
from app.routers import catalog, prediction, recommend

app = FastAPI(title=APP_NAME, version=MODEL_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],      # 11-13 보안: 화면이 쓰는 것만 (예전 "*")
    allow_headers=["Content-Type"],
)

app.include_router(catalog.router)
app.include_router(prediction.router)
app.include_router(recommend.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}
