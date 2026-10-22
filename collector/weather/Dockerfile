# 날씨 수집기 + 통합 전처리 (데이터 담당 코드). 저장소 맨 위에서 빌드한다: docker compose 의 weather-collector
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 TZ=Asia/Seoul DATA_DIR=/app/collector/weather/data
WORKDIR /app/collector/weather
COPY collector/weather/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY collector/weather/ ./

# 시간표대로 run.py 실행 (예보 3시간마다, 관측·전처리 매일 10:40). 원본·결과는 data/ (도커 볼륨 weatherraw)
CMD ["python", "scheduler.py"]
