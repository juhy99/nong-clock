@echo off
chcp 65001 >nul
rem 이사 꾸러미 만들기 (11-16): 코드(push 안 한 커밋 포함) · DB 백업 · 자료 · 모델 · 분석 노트북을 한 폴더에
rem Docker Desktop 과 DB(nong-clock-db)가 켜져 있어야 함. 매일_예측_갱신.bat 이 끝난 뒤에 돌리세요
rem 다른 곳에 만들려면: 이사_꾸러미_만들기.bat E:\농클락_이사
py -3 -X utf8 "%~dp0이사_꾸러미.py" %*
pause
