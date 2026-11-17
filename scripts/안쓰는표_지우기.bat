@echo off
chcp 65001 >nul
setlocal
rem ============================================================
rem  안 쓰는 표 지우기 (11-17) — 이미 만들어진 DB 에서 한 번만
rem  화면·예측 어디에서도 읽지 않는 수집 표 12개를 지운다. 새로 만드는 DB 에는 처음부터 없음 (schema.sql 에서 뺌)
rem    index_group grade_map holiday price_index_daily weather_daily weather_normal
rem    weather_region_now garak_inout_daily shipment_reservation_daily fx_daily policy_doc collect_log
rem  회원·게시판·시세·예측 표는 건드리지 않음. 지운 표는 되돌릴 수 없음 (원자료 파일은 자료 폴더에 그대로 있음)
rem ============================================================
set "PSQL=docker exec -i -e PGCLIENTENCODING=UTF8 nong-clock-db psql -U postgres -d farmdb -v ON_ERROR_STOP=1"
echo 지울 표와 들어 있는 줄 수 (아무것도 안 나오면 이미 지워진 것):
%PSQL% -c "SELECT relname AS 표, n_live_tup AS 줄수_대략 FROM pg_stat_user_tables WHERE relname IN ('index_group', 'grade_map', 'holiday', 'price_index_daily', 'weather_daily', 'weather_normal', 'weather_region_now', 'garak_inout_daily', 'shipment_reservation_daily', 'fx_daily', 'policy_doc', 'collect_log') ORDER BY 1" || (echo [멈춤] DB 에 연결하지 못했어요. docker compose up -d 로 켜져 있는지 확인해 주세요 & goto end)
echo.
set /p ANS=위 표들을 지울까요? (Y 를 누르고 Enter, 그만두려면 그냥 Enter): 
if /i not "%ANS%"=="Y" (echo 지우지 않았어요. & goto end)
%PSQL% -c "DROP TABLE IF EXISTS index_group, grade_map, holiday, price_index_daily, weather_daily, weather_normal, weather_region_now, garak_inout_daily, shipment_reservation_daily, fx_daily, policy_doc, collect_log" && (echo 지웠어요.) || (echo [멈춤] 지우지 못했어요. 위 오류를 확인해 주세요)
echo.
echo 남은 표:
%PSQL% -c "SELECT string_agg(table_name, ', ' ORDER BY table_name) FROM information_schema.tables WHERE table_schema = 'public'"
:end
pause
