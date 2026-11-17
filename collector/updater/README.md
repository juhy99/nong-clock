# 갱신 서비스 (price-updater) — 관리자 화면에서 가격 수집·예측 돌리기

관리자 사이트 **데이터 수집** 화면 맨 위 "데이터 갱신" 카드의 버튼을 받아, 이 컨테이너 안에서 실행합니다.
예전에는 PC 에서 `scripts\매일_예측_갱신.bat` · `scripts\매달_v4_만들기.bat` 을 손으로 돌렸습니다 (그 bat 도 그대로 쓸 수 있음 — 같은 순서).

| 버튼 | 하는 일 | 걸리는 시간 |
|---|---|---|
| **지금 갱신** | 자료 받기(`collect.py auction · kamis · warning · sanji` — 시세 화면·예측이 읽는 것만, 실패해도 계속) → DB 표 만들기(`build_tables.py`) → DB 에 넣기(`load_db.py --init`) → 예측 만들기(`python-ml/run_daily.py`) | 약 20분 |
| **월 예측 만들기** | 추가 자료(`collect_monthly.py all`, 실패해도 계속) → v4(`model/run_model.py monthly`) → 결과를 `model/v4` 로 → 위 "지금 갱신" 전부 | 약 10분 + 위 |
| **PDF 올리기** | 관측월보 PDF 를 자료 폴더 `manual/월보/` 에 저장 (이름 `VC·VS·VPO·F` + 연월 6자리, 50MB 까지) | 바로 |

- 날씨 관측·예보는 `weather-collector` 컨테이너가 따로 받으므로 여기서는 받지 않습니다 (같은 인증키 호출 한도를 두 번 쓰지 않게). 공휴일·aT 출하예약·가락 반입량·환율·수급 정책은 화면·예측이 읽지 않아 받지 않습니다 — 전부 받으려면 `scripts\매일_예측_갱신.bat`.
- 한 번에 하나만 돕니다. 도는 중에 또 누르면 "이미 갱신 중이에요".
- 월 예측은 **원장 마지막 날이 3일 이후**이고 그 기준월을 아직 안 만들었을 때만 버튼이 켜집니다 (`run_model.py` 와 같은 규칙).
- **알림**: 갱신이 실패했거나 끊겼을 때, 받지 못한 자료가 있을 때, 전날 경매 자료가 아직 안 올라왔거나 덜 올라왔을 때(시장 16곳 미만), 예측 기준일이 4일 넘게 멈췄을 때 관리자 첫 화면과 이 카드 맨 위에 띄웁니다 → [지금 갱신] 을 다시 누르면 됩니다. 자동 실행은 하루 한 번만 시도합니다.
- 화면을 닫아도 계속 돕니다. 컨테이너가 도중에 꺼지면 그 실행은 "중단됨"으로 남습니다.

## 처음 한 번 (서버 또는 PC)

1. **`.env` 에 넣기** (저장소 맨 위, 커밋 금지). 윈도우는 `scripts\갱신서비스_처음설정.bat` 이 아래 1)~3)을 대신 넣어 줍니다 (값을 화면에 보이지 않음).
   ```
   UPDATER_TOKEN=...            # 1) 아무도 모르는 긴 글자.  만들기: python -c "import secrets;print(secrets.token_hex(24))"
   NC_DATA_ROOT=D:\nong-clock-data   # 2) 자료 폴더 (안에 05_DB적재\data 가 있어야 함)
   MAFRA_API_KEY=...            # 3) 수집 인증키 — collector\daily\.env 에 있는 것과 같은 값 (키_발급_따라하기.md)
   KAMIS_KEY=...
   KAMIS_ID=...
   # (있으면) KOSIS_API_KEY · ECOS_API_KEY · SEOUL_OPENAPI_KEY — 없으면 그 자료만 건너뜀
   # UPDATER_DAILY_AT=06:00     # 매일 자동 실행을 켤 때만. 비워 두면 버튼으로만 (기본)
   ```
2. **깃에 없는 것 두 가지를 자료 폴더로** — `<자료 폴더>\05_DB적재\data\v4_seed\`
   - `collector\daily\model\seed\` 안의 것 전부 (v4 seed. 없으면 "월 예측 만들기" 만 꺼짐)
   - `collector\daily\tools\tessdata\kor.traineddata` → `v4_seed\tessdata\kor.traineddata` (월보 OCR. 없으면 컨테이너에 설치된 한국어 자료를 씀)
3. `docker compose up -d --build`

## 안전 장치

- 밖으로 열지 않습니다 (`expose` 만, `ports` 없음). backend(Spring 관리자 API)만 부르고, 그때도 `X-Updater-Token` 이 `.env` 의 `UPDATER_TOKEN` 과 같아야 합니다. 토큰이 비어 있으면 모든 요청을 거절합니다.
- 인증키·비밀번호 값은 응답·기록 어디에도 남기지 않습니다 (`*_KEY` · `*_ID` · `SECRET` · `TOKEN` · `PASSWORD` 환경 변수 값은 `***`).
- 기록: `<자료 폴더>\05_DB적재\data\log\updater_runs.json` (최근 50번) · `log\updater\<시각>_<종류>.txt` (단계별 출력 전체)

## 내 PC 에서 시험

```
cd collector\updater
python -m pytest tests -q        # 35 passed (표준 라이브러리만 씀, pytest 만 필요)
```

| 파일 | 내용 |
|---|---|
| `runner.py` | 단계 실행기: 한 번에 하나 · 출력 기록 · 키 가림 · 중단 표시 |
| `state.py` | 상태 읽기(기준일 · v4 기준월 · 자료별 결과 · 월보) · 월보 파일 받기 |
| `jobs.py` | 단계 정의 (bat 과 같은 순서) · v4 결과를 `model/v4` 로 |
| `server.py` | HTTP `:8090` — `GET /status` · `POST /run/daily` · `POST /run/monthly` · `POST /wolbo?name=` · 자동 실행 |
