#!/bin/sh
# cron (서버 한국시간):
#   40 7 * * *                    /경로/run_daily.sh >> /경로/data/log/cron.log 2>&1
#   20 2,5,8,11,14,17,20,23 * * * cd /경로 && python3 collect.py fcst >> data/log/cron.log 2>&1
cd "$(dirname "$0")" || exit 1
python3 collect.py daily
python3 build_tables.py
python3 load_db.py
