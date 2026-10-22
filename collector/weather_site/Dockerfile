# 날씨 화면 파일 만들기. 저장소 맨 위에서 빌드한다: docker compose 의 weather-export
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app/collector/weather_site
COPY collector/weather_site/*.py ./

# 10분마다 input/날씨_대통합.csv (서버 폴더를 읽기 전용으로 연결)가 바뀌었는지 보고 data/ (도커 볼륨 weatherdata)에 다시 만든다
CMD ["python", "export_weather.py", "--loop"]
