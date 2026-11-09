@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -X utf8 collect.py test
pause
