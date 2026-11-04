# ML API. 저장소 맨 위에서 빌드한다 (shared/ 의 품목·도매시장·흙 pH 목록이 필요): docker compose 의 ml-api
FROM python:3.12-slim

WORKDIR /app

COPY ml-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/items.json shared/markets.json shared/soil_ph.json shared/
COPY ml-api/app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
