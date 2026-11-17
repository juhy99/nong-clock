# 갱신 서비스: 관리자 화면의 [지금 갱신]·[월 예측 만들기]·[PDF 올리기] 를 받아 수집 → 표 → DB → 예측을 돌린다
# 저장소 맨 위에서 빌드: docker compose 의 price-updater (collector/updater/README.md)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 TZ=Asia/Seoul
# poppler(pdftotext)·tesseract(한글 OCR) = 월보 PDF 읽기, libgomp1 = lightgbm
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-kor libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY collector/updater/requirements.txt collector/updater/requirements.txt
RUN pip install --no-cache-dir -r collector/updater/requirements.txt
COPY shared/ shared/
COPY python-ml/ python-ml/
COPY collector/daily/ collector/daily/
COPY collector/updater/ collector/updater/
# 한글 OCR 자료: 저장소에 없으면(깃 제외) 방금 설치한 것을 가리키게. 자료 폴더 v4_seed/tessdata 가 있으면 켤 때 그것을 먼저 씀 (server.py)
RUN ln -s "$(dirname "$(find /usr/share -name kor.traineddata | head -1)")" /app/collector/daily/tools/tessdata_system

EXPOSE 8090
CMD ["python", "-u", "collector/updater/server.py"]
