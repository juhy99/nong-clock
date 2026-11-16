@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  매달 월 예측(v4) 직접 만들기 (11-16, 팀원 민철 재현 묶음 → collector\daily\model)
rem  언제: 매달 3일 이후 (원장 정산이 다 올라온 뒤). 원장 마지막 날의 앞 달이 기준월이 됨
rem  순서: 1) 버전 확인  2) 주산지 기상·통계청·월보 확인 (실패해도 계속)  3) v4 만들기 (약 10분)
rem        4) 결과를 model\v4 에 넣기  5) 매일_예측_갱신.bat 으로 예측 표·DB 갱신
rem  월보: aglook.krei.re.kr 에서 그달 호 PDF 4개(VC·VS·VPO·F + YYYYMM)를 %DATA%\manual\월보 에 넣기
rem  처음 한 번: py -3 -m pip install lightgbm==4.7.0 scikit-learn==1.9.1 scipy pypdf lxml
rem  기준월을 직접 정하려면: 매달_v4_만들기.bat 2026-11
rem ============================================================
set "DATA_ROOT=%NC_DATA_ROOT%"
if "%DATA_ROOT%"=="" if exist "D:\nong-clock-data\05_DB적재\data" set "DATA_ROOT=D:\nong-clock-data"
if "%DATA_ROOT%"=="" if exist "C:\finalproject\nong-clock-data\05_DB적재\data" set "DATA_ROOT=C:\finalproject\nong-clock-data"
if "%DATA_ROOT%"=="" set "DATA_ROOT=D:\nong-clock-data"
set "DATA=%DATA_ROOT%\05_DB적재\data"
set "WORK=%DATA%\v4_작업"
for %%i in ("%~dp0..") do set "REPO=%%~fi"
set "COL=%REPO%\collector\daily"
echo 데이터 폴더: %DATA%
echo v4 작업 폴더: %WORK%

echo [1] 파이썬 패키지 버전 (lightgbm 4.7.0 · scikit-learn 1.9.1 권장)
py -3 -X utf8 "%COL%\model\버전보기.py"
py -3 -c "import lightgbm, sklearn, scipy, pypdf, lxml" 2>nul || (echo [멈춤] 패키지가 없어요: py -3 -m pip install lightgbm==4.7.0 scikit-learn==1.9.1 scipy pypdf lxml & goto fail)
if not exist "%COL%\model\seed\원장_일별_줄오류만_seed.csv.gz" (echo [멈춤] seed 가 없어요: %COL%\model\seed — 민철 재현 묶음 zip 의 model\seed 를 넣어 주세요 & goto fail)

echo [2] 추가 자료 (주산지 기상 · 통계청 · 월보 확인) — 실패해도 이어감
cd /d "%COL%"
set "FARMBID_DATA=%DATA%"
py -3 -X utf8 collect_monthly.py all || echo [주의] 받지 못한 자료가 있어요. 받은 자료와 seed 로 계속합니다

echo [3] v4 만들기 (원장 → 패널 → f1 → f2, 약 10분)
set "BASEOPT="
if not "%~1"=="" set "BASEOPT=--base %~1"
py -3 -X utf8 model\run_model.py monthly --raw "%DATA%\raw\auction" --data "%WORK%" %BASEOPT% || goto fail

echo [4] 결과를 model\v4 에 넣기
set "RES="
for /f "usebackq delims=" %%r in ("%WORK%\결과\_최신.txt") do set "RES=%%r"
if "%RES%"=="" (echo [멈춤] 결과 폴더를 못 찾았어요 & goto fail)
if not exist "%DATA%\model\v4" mkdir "%DATA%\model\v4"
set "GOT="
for %%f in ("%RES%\결과_기준*\01_322_월예측_*.csv") do (
  if exist "%DATA%\model\v4\%%~nxf" if not exist "%DATA%\model\v4\%%~nf_직접만들기전.csv.bak" copy /y "%DATA%\model\v4\%%~nxf" "%DATA%\model\v4\%%~nf_직접만들기전.csv.bak" >nul
  copy /y "%%f" "%DATA%\model\v4\%%~nxf" >nul
  echo    넣음: %DATA%\model\v4\%%~nxf
  set "GOT=1"
)
if "%GOT%"=="" (echo [멈춤] 월 예측 파일이 없어요: %RES% & goto fail)

echo [5] 예측 표 · DB 갱신 (매일_예측_갱신.bat)
call "%~dp0매일_예측_갱신.bat" auto || goto fail
echo.
echo 끝. 화면: http://localhost:5173/ai
pause
exit /b 0

:fail
echo [멈춤] 위 오류를 확인하세요. 실행 기록: %WORK%\work\_log_*.txt
pause
exit /b 1
