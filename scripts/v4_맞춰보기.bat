@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  v4 맞춰보기 (11-16): 원자료 없이 seed 만으로 기준월 2026-10 을 다시 만들어
rem  팀원 76판(지금 사이트가 쓰는 v4)과 숫자가 같은지 확인. 실제 예측·DB 는 건드리지 않음
rem  "결과: 같음 (모든 숫자 차이 0)" 이 나오면 이 PC 에서도 같은 v4 가 만들어지는 것
rem ============================================================
for %%i in ("%~dp0..") do set "REPO=%%~fi"
set "M=%REPO%\collector\daily\model"
set "T=%TEMP%\nongclock_v4_맞춰보기"
if exist "%T%" rmdir /s /q "%T%"
mkdir "%T%"
py -3 -X utf8 "%M%\버전보기.py"
py -3 -X utf8 "%M%\run_model.py" monthly --base 2026-10 --no-raw --data "%T%\model" || goto fail
py -3 -X utf8 "%M%\맞춰보기.py" "%M%\seed\결과_기준202610\01_322_월예측_기준202610_앞으로12달.csv" "%T%\model\결과\NongClock_자동_기준202610\결과_기준202610\01_322_월예측_기준202610_앞으로12달.csv" || goto fail
pause
exit /b 0
:fail
echo [멈춤] 위 오류를 확인하세요
pause
exit /b 1
