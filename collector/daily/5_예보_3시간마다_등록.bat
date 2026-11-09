@echo off
chcp 65001 >nul
rem 단기·중기예보는 API가 최근 24시간 발표분만 줘서 3시간마다 받아야 빠짐없음 (02:20부터 3시간 간격)
schtasks /Create /F /SC HOURLY /MO 3 /ST 02:20 /TN "FarmBid_예보" /TR "py -3 -X utf8 \"%~dp0collect.py\" fcst"
echo 3시간마다 예보를 받도록 등록했습니다. (해제: schtasks /Delete /TN FarmBid_예보 /F)
pause
