@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -X utf8 collect.py daily
py -3 -X utf8 build_tables.py
py -3 -X utf8 load_db.py
if "%1"=="" pause
