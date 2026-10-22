# 서버용 화면: 빌드한 사용자·관리자 사이트를 nginx 로 띄운다. 저장소 맨 위에서 빌드 (shared/ 필요): docker compose 의 web
FROM node:20-alpine AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY shared /app/shared
COPY frontend ./
# 같은 서버의 nginx 가 /ml → ml-api, /data → 수집한 뉴스 파일로 연결한다 (nginx.conf)
ARG VITE_ML_API_BASE=/ml
ARG VITE_NEWS_URL=/data/news-recent.json
ENV VITE_ML_API_BASE=$VITE_ML_API_BASE VITE_NEWS_URL=$VITE_NEWS_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
