@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  매일 예측 갱신 (11-12): 1) 수집 → 표(최근 14일) → DB   2) 원인 엔진 · 팀원 일 모델 · 섞기 → 예측 표 → DB
rem  Docker 의 DB 가 켜져 있어야 함. 처음 한 번: py -3 -m pip install pandas numpy psycopg2-binary
rem  자동으로 매일: 작업 스케줄러에 이 파일을 "auto" 인자로 등록 (예: 새벽 6시 — 경매 정산 자료가 전날까지 올라온 뒤)
rem  표는 tables_daily 폴더에 씀 (tables 폴더의 2020년부터 전체 파일을 덮어쓰지 않게)
rem ============================================================
set "DATA=D:\nong-clock-data\05_DB적재\data"
for %%i in ("%~dp0..") do set "REPO=%%~fi"

echo [A] 수집 → 표 → DB
cd /d "%REPO%\collector\daily"
set "FARMBID_DATA=%DATA%"
set "FARMBID_OUT=%DATA%\tables_daily"
rem 11-13: 자료 하나가 실패해도(키 없음 · 사이트 점검 등) 멈추지 않고 이어감 — 받은 것만으로 표를 만들고 예측함. 실패는 data\log\collect_log.csv
py -3 -X utf8 collect.py daily || echo [주의] 수집 중 실패한 자료가 있어요. 받은 자료로 계속합니다 (collect_log.csv 확인)
py -3 -X utf8 build_tables.py || goto fail
rem --init: 표 정의(schema.sql)를 먼저 실행 — 새 열(예: 11-13 price_forecast_daily.off_season)이 예전 DB 에도 생김. 이미 있으면 그대로
py -3 -X utf8 load_db.py --init || goto fail

echo [B] 예측 (python-ml\run_daily.py)
set "FARMBID_OUT="
cd /d "%REPO%"
py -3 -X utf8 python-ml\run_daily.py || goto fail
echo.
echo 끝. 화면: http://localhost:5173/ai
if "%1"=="" pause
exit /b 0

:fail
echo [멈춤] 위 오류를 확인하세요. 예측만 다시: py -3 python-ml\run_daily.py --from 5
if "%1"=="" pause
exit /b 1
