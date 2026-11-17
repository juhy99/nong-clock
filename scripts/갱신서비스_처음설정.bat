@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  갱신 서비스(price-updater) 처음 설정 (11-17) — 관리자 화면 [지금 갱신] 을 쓰기 전에 한 번
rem  저장소 맨 위 .env 에 아래를 넣는다 (이미 있으면 건드리지 않음, 값은 화면에 보이지 않음)
rem    UPDATER_TOKEN  새로 만든 긴 글자
rem    NC_DATA_ROOT   자료 폴더
rem    MAFRA_API_KEY · KAMIS_KEY · KAMIS_ID 등 수집 인증키 — collector\daily\.env 에 있는 줄을 그대로 복사
rem  그리고 깃에 없는 v4 seed · 한글 OCR 자료를 자료 폴더 v4_seed 로 복사
rem ============================================================
for %%i in ("%~dp0..") do set "REPO=%%~fi"
set "ENV=%REPO%\.env"
set "CENV=%REPO%\collector\daily\.env"
if not exist "%ENV%" (echo [멈춤] %ENV% 가 없어요. 먼저 copy .env.example .env 후 DB_PASSWORD 등을 채워 주세요 & goto end)

set "DATA_ROOT=%NC_DATA_ROOT%"
if "%DATA_ROOT%"=="" if exist "D:\nong-clock-data\05_DB적재\data" set "DATA_ROOT=D:\nong-clock-data"
if "%DATA_ROOT%"=="" if exist "C:\finalproject\nong-clock-data\05_DB적재\data" set "DATA_ROOT=C:\finalproject\nong-clock-data"
if "%DATA_ROOT%"=="" (echo [멈춤] 자료 폴더를 못 찾았어요. set NC_DATA_ROOT=자료폴더 후 다시 실행해 주세요 & goto end)

rem 마지막 줄이 줄바꿈 없이 끝나 있어도 새 줄이 붙지 않게 빈 줄을 먼저 넣음
echo.>>"%ENV%"

findstr /b /c:"UPDATER_TOKEN=" "%ENV%" >nul && (echo [그대로] UPDATER_TOKEN 이미 있음) || (
  py -3 -c "import secrets;print('UPDATER_TOKEN='+secrets.token_hex(24))" >>"%ENV%" && (echo [넣음] UPDATER_TOKEN 새로 만듦) || (echo [멈춤] 파이썬 py -3 이 없어요. .env 에 UPDATER_TOKEN=긴글자 를 직접 넣어 주세요)
)
findstr /b /c:"NC_DATA_ROOT=" "%ENV%" >nul && (echo [그대로] NC_DATA_ROOT 이미 있음) || (
  echo NC_DATA_ROOT=%DATA_ROOT%>>"%ENV%"
  echo [넣음] NC_DATA_ROOT=%DATA_ROOT%
)
if not exist "%CENV%" (echo [주의] %CENV% 가 없어요 — 수집 인증키는 .env 에 직접 넣어 주세요 & goto seed)
for %%k in (MAFRA_API_KEY KAMIS_KEY KAMIS_ID KOSIS_API_KEY ECOS_API_KEY SEOUL_OPENAPI_KEY) do (
  findstr /b /c:"%%k=" "%ENV%" >nul && (echo [그대로] %%k 이미 있음) || (
    findstr /b /c:"%%k=" "%CENV%" >>"%ENV%" && (echo [넣음] %%k) || (echo [없음] %%k — collector\daily\.env 에 없어요. 그 자료는 건너뜁니다)
  )
)

:seed
set "BUNDLE=%DATA_ROOT%\05_DB적재\data\v4_seed"
if exist "%REPO%\collector\daily\model\seed\원장_일별_줄오류만_seed.csv.gz" (
  robocopy "%REPO%\collector\daily\model\seed" "%BUNDLE%" /e /xo /njh /njs /ndl /nfl /np >nul
  echo [복사] v4 seed → %BUNDLE%
) else (echo [주의] collector\daily\model\seed 가 없어요 — "월 예측 만들기" 버튼만 꺼집니다)
if exist "%REPO%\collector\daily\tools\tessdata\kor.traineddata" (
  if not exist "%BUNDLE%\tessdata" mkdir "%BUNDLE%\tessdata"
  copy /y "%REPO%\collector\daily\tools\tessdata\kor.traineddata" "%BUNDLE%\tessdata\" >nul
  echo [복사] 한글 OCR 자료 → %BUNDLE%\tessdata
)
echo.
echo 끝. 이제:  docker compose up -d --build
:end
pause
