# 뉴스 수집기. 저장소 맨 위에서 빌드한다 (shared/news_rules.json 이 필요): docker compose 의 news-collector
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY shared/news_rules.json shared/news_rules.json
COPY collector/news/*.py collector/news/

WORKDIR /app/collector/news
# 켜자마자 한 번 모으고, 그 뒤 1시간마다. 기사는 data/ (도커 볼륨 newsdata)에 쌓인다
CMD ["python", "collect_news.py", "--loop"]
