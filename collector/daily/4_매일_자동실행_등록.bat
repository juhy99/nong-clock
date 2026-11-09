@echo off
chcp 65001 >nul
schtasks /Create /F /SC DAILY /ST 07:40 /TN "FarmBid_일일수집" /TR "\"%~dp02_매일_실행.bat\" auto"
echo 매일 07:40 에 2_매일_실행.bat 이 돌도록 등록했습니다. (해제: schtasks /Delete /TN FarmBid_일일수집 /F)
pause
