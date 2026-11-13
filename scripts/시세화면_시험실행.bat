@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  시세 화면을 실제 데이터로 보기 (내 PC 시험용, 2026-11-09)
rem  1) 도커로 DB + Spring(backend) + AI 예측(ml-api, DB 예측기) 켜기  2) 수집기 표(CSV)를 DB에 넣기  3) 화면(npm run dev) 켜기
rem  데이터 폴더가 다르면 아래 DATA 한 줄만 고치세요. (저장소 위치는 이 파일 위치로 자동)
rem ============================================================
set "DATA=D:\nong-clock-data\05_DB적재\data"
for %%i in ("%~dp0..") do set "REPO=%%~fi"

docker version >nul 2>&1
if errorlevel 1 ( echo [멈춤] Docker Desktop 이 켜져 있지 않아요. Docker Desktop 을 켜고 다시 실행하세요. & pause & exit /b 1 )
if not exist "%DATA%\tables\price_daily.csv" ( echo [멈춤] %DATA%\tables 에 시세 표가 없어요. DATA 경로를 확인하세요. & pause & exit /b 1 )

cd /d "%REPO%"
if not exist ".env" ( echo [멈춤] %REPO%\.env 가 없어요 ^(.env.example 을 복사하고 DB_PASSWORD 를 채우세요^) & pause & exit /b 1 )
for /f "tokens=1,* delims==" %%a in ('findstr /b "DB_PASSWORD=" .env') do set "DB_PASSWORD=%%b"

echo [1/3] DB · Spring · AI 예측^(ml-api^)을 켜는 중 ^(처음엔 빌드로 몇 분 걸려요^)...
rem 예측기를 DB 예측기로 (가격 예측 = DB 의 price_forecast_monthly). 서버 기본은 dummy 그대로
set "PREDICTOR=db"
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile spring up -d --build db backend ml-api
if errorlevel 1 ( echo [멈춤] docker compose 실패. 위 오류를 확인하세요. & pause & exit /b 1 )

echo     DB 가 준비될 때까지 기다리는 중...
for /l %%i in (1,1,60) do (
  docker exec nong-clock-db pg_isready -U postgres -d farmdb >nul 2>&1 && goto dbready
  timeout /t 2 >nul
)
echo [멈춤] DB 가 2분 안에 준비되지 않았어요. docker compose logs db 로 확인하세요.
pause & exit /b 1
:dbready

echo [2/3] 수집기 표^(%DATA%\tables^)를 DB 에 넣는 중 ^(1~3분^)...
rem 폴더를 도커에 직접 붙이면(-v) PC 설정에 따라 빈 폴더로 보일 때가 있어서, 컨테이너를 만든 뒤 파일을 복사해 넣는다
rem price_unit_daily 는 tables 에 전 기간이 있으니 DB 표를 비우고 다시 넣음 (단위 정의를 바꿔도 옛 줄이 안 남게, 11-12)
call :load "%DATA%\tables" price_unit_daily || ( pause & exit /b 1 )
rem 덧붙임 폴더 (11-12): tables_* (예: tables_1112 = 그 뒤 받은 시세 + 일 단위 예측 표) 가 있으면 이름 순서로 이어서 넣음 (같은 날짜는 덮어씀)
for /d %%f in ("%DATA%\tables_*") do ( call :load "%%~ff" || ( pause & exit /b 1 ) )
docker compose -f docker-compose.yml -f docker-compose.local.yml --profile spring up -d backend >nul

echo [3/3] 화면 켜기
cd /d "%REPO%\frontend"
findstr /b "VITE_PRICE_SOURCE=db" .env >nul 2>&1 || ( echo [알림] frontend\.env 에 VITE_PRICE_SOURCE=db 가 없으면 화면은 가짜 시세를 보여 줘요 )
echo     화면 부품^(node_modules^)을 package.json 에 맞추는 중 ^(처음엔 1~2분^)...
call npm install --no-audit --no-fund
if errorlevel 1 ( echo [멈춤] npm install 실패. 위 오류를 확인하세요. & pause & exit /b 1 )
start "farmbid-web (끄려면 이 창 닫기)" cmd /k "npm run dev"
timeout /t 8 >nul
start "" "http://localhost:5173/market"
echo.
echo 끝. 브라우저에 시세 화면이 열려요. 안 열리면 http://localhost:5173/market
echo 시세 API 확인: http://localhost:8080/api/prices/today  ^(Spring 이 켜지는 데 30초쯤 걸려요^)
echo AI 예측 확인: http://localhost:8000/docs  ^(POST /predict 에 item=peach, variety=peach-1 등^)
echo 가격 예측 화면: http://localhost:5173/ai  ^(로그인 필요 · 일 단위 예측 = DB 의 price_forecast_daily^)
echo Spring 오류 보기: docker compose logs backend
pause
exit /b 0


:load
rem 표 폴더 하나를 DB 에 넣기 (%1 = 폴더, %2 = 비우고 넣을 표 이름들, 없으면 덮어쓰기만)
echo     넣는 중: %~1
docker rm -f farmbid-loader >nul 2>&1
rem 11-13 보안: DB 포트를 이 컴퓨터 안(127.0.0.1)에만 열어서, 적재 컨테이너는 DB 와 같은 도커 내부망에 붙어 이름(db)으로 접속
set "NCNET="
for /f "delims=" %%n in ('docker inspect nong-clock-db --format "{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}"') do set "NCNET=%%n"
if not defined NCNET ( echo [멈춤] DB 컨테이너^(nong-clock-db^)의 도커 내부망을 찾지 못했어요. & exit /b 1 )
docker create --name farmbid-loader --network "%NCNET%" -w /app ^
  -e FARMBID_DATA=/tmp/fd -e FARMBID_OUT=/tables -e PGHOST=db -e PGPORT=5432 -e PGDATABASE=farmdb -e PGUSER=postgres -e "PGPASSWORD=%DB_PASSWORD%" -e "NC_REPLACE=%~2" ^
  python:3.12-slim sh -c "pip install -q --root-user-action=ignore --disable-pip-version-check psycopg2-binary && python load_db.py --init" >nul
if errorlevel 1 ( echo [멈춤] 적재용 컨테이너를 만들지 못했어요. & exit /b 1 )
docker cp "%REPO%\collector\daily\." farmbid-loader:/app
if errorlevel 1 ( echo [멈춤] 수집기 코드를 복사하지 못했어요: %REPO%\collector\daily & docker rm -f farmbid-loader >nul & exit /b 1 )
docker cp "%~1\." farmbid-loader:/tables
if errorlevel 1 ( echo [멈춤] 적재용 CSV 를 복사하지 못했어요: %~1 & docker rm -f farmbid-loader >nul & exit /b 1 )
docker start -a farmbid-loader
set "LOADRC=%errorlevel%"
docker rm -f farmbid-loader >nul 2>&1
if not "%LOADRC%"=="0" ( echo [멈춤] 적재 실패: %~1. 위 오류를 확인하세요. & exit /b 1 )
exit /b 0
