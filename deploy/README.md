# 팀 서버 컴퓨터 (Windows) 운영

서버 컴퓨터는 **수집·저장·화면을 계속 켜 두는 곳**, 각자 PC 는 **코드를 고쳐 push 하고 서버에 접속하는 곳**입니다.

```
[내 PC] 코드 수정 → push → PR → main 합침 ─▶ [GitHub] ─(10분마다 확인)─▶ [서버 컴퓨터] docker compose
   └─ 브라우저: http://서버주소  ◀──────────────────────────────── 화면 · 수집한 뉴스 · ML API · DB
```

| 서비스 | 하는 일 | 주소 (서버 안에서) |
|---|---|---|
| `web` | 사용자·관리자 화면 (빌드본) | `http://localhost` · `/admin/` |
| `web` → `/data/` | 수집한 뉴스 파일 (읽기 전용) | `/data/news-recent.json` (7일) · `/data/news.json` (90일) · `/data/collect_log.json` (수집 기록) · `/data/rejected.json` (거른 기사) |
| `web` → `/data/weather/` | 날씨 화면 파일 (읽기 전용) | `/data/weather/meta.json` (상태) · `regions-daily.json` · `regions-monthly.json` · `collect_log.json` (날씨 수집 기록) |
| `web` → `/ml/` | ML API 중계 | `/ml/items` |
| `news-collector` | 켜자마자 한 번, 그 뒤 1시간마다 뉴스 수집 | — |
| `weather-collector` | 날씨 수집(예보 3시간마다, 관측·장기전망 매일 10:40) + 통합 전처리 → 볼륨 `weatherraw` | — |
| `weather-export` | 5분마다 전처리 결과(날씨 CSV)가 바뀌었는지 보고 화면 파일로 다시 만듦 | — |
| `ml-api` | AI 예측 | `:8000` |
| `db` | Postgres | `:5432` |

서버에서 코드를 직접 고치지 않습니다. 고치면 자동 배포가 멈춥니다 (덮어쓰지 않으려고).

## 1. 처음 한 번: 서버 준비

1. **설치:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (WSL2 사용), [Git for Windows](https://git-scm.com/download/win)
2. **Docker Desktop 설정 → General → "Start Docker Desktop when you sign in"** 켜기
3. **전원:** 설정 → 시스템 → 전원 → 화면·절전 "안 함". 서버는 로그인한 상태로 둔다 (Docker Desktop 이 로그인한 사용자로 돌기 때문)
4. **저장소 받기** (경로에 한글·띄어쓰기 없는 곳):
   ```powershell
   git clone https://github.com/juhy99/nong-clock.git C:\farmbid
   cd C:\farmbid
   copy .env.example .env
   notepad .env      # DB_PASSWORD, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 채우기 (커밋 금지)
   ```
   저장소가 비공개면 `git clone` 때 GitHub 로그인 창이 한 번 뜹니다 (이후 자동 배포도 그 로그인을 씀).
5. **첫 실행:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -Force
   ```
   처음엔 이미지 빌드로 몇 분 걸립니다. 끝나면 서버에서 `http://localhost` 가 열리고, 1~2분 뒤 `http://localhost/data/collect_log.json` 에 첫 수집 기록이 보입니다.
6. **자동 배포 켜기** (10분마다 main 확인 → 바뀌었으면 받아서 다시 빌드):
   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy\register-auto-deploy.ps1
   ```

## 1-1. 날씨 수집기 처음 한 번 (데이터 담당 코드 `collector/weather`)

`weather-collector` 가 예보를 3시간마다(02:20·05:20·…·23:20), 관측·장기전망 수집과 전처리를 매일 10:40 에 돌립니다 (`collector/weather/scheduler.py`).
원본·결과는 도커 볼륨 `weatherraw` 에 쌓이고, `weather-export` 가 전처리 결과(`날씨_대통합_일별.csv`)를 화면 파일로 바꿉니다.

1. **키 넣기** — 서버 `C:\farmbid\.env` 에 두 줄 (값은 데이터 담당에게 직접 받기, 커밋·메신저 캡처 금지)
   ```
   KMA_APIHUB_KEY=...     # 기상청 API허브 (ASOS·AWS)
   DATA_GO_KR_KEY=...     # 공공데이터포털 Decoding 키 (농업기상·단기·중기예보)
   ```
   이 PR 이 합쳐지기 전에 넣어 두면 자동 배포 때 바로 씁니다. 나중에 넣었다면 `docker compose up -d weather-collector`.
2. **배포** — PR 이 main 에 합쳐지면 자동 배포 (또는 `deploy\deploy.ps1`). 데이터 폴더가 비어 있으면 수집기는 **바로 수집하지 않고 기다립니다**
   (`docker compose logs weather-collector` 에 "처음 켜짐" 표시).
3. **데이터 담당 PC 에서 받은 파일 옮기기** (다시 받을 수 없는 것 포함, 목록은 `collector/weather/README.md` 8번)
   - 서버에 `C:\weather-init\data\` 폴더를 만들고 README 8번의 "서버에 둘 곳" 그대로 넣는다. 예:
     ```
     C:\weather-init\data\raw\fcst\진행상태.sqlite3          ← 단기·중기예보 원본 DB (가장 중요)
     C:\weather-init\data\raw\longrange\pdf\…                ← 장기전망 PDF
     C:\weather-init\data\integrated\01_원본\ASOS\…           ← ASOS 1991~2014 zip (평년값)
     C:\weather-init\data\raw\asos\… · raw\aws\원본\… · raw\agri\진행상태.sqlite3   ← (있으면) 관측 원본, 호출 절약
     ```
   - 볼륨으로 복사 (PowerShell, `C:\farmbid` 에서):
     ```powershell
     docker compose stop weather-collector
     docker cp C:\weather-init\data\. nong-clock-weather-collector:/app/collector/weather/data/
     docker compose start weather-collector
     ```
   - 다시 켜지면 예보를 바로 받고, 전처리 기록이 없으니 관측 수집 → 전처리를 바로 한 번 돌립니다 (처음엔 오래 걸릴 수 있음).
4. **관측 원본을 옮기지 않았다면** 과거분을 한 번 받기 (API허브 약 300회 + 농업기상):
   ```powershell
   docker compose exec weather-collector python run.py collect --backfill --only asos,aws,agri
   docker compose exec weather-collector python run.py preprocess
   ```
5. **확인**
   - `docker compose logs -f weather-collector` → `[fcst] 정상 | 호출 … | 추가 …`, `[전처리] 대통합일별: 종료코드 0`
   - 관리자 › 데이터 수집: 단기·중기예보 / 지난 날씨 / 장기전망이 **서버 수집 · 정상**, 서버 상태의 "날씨 수집기" 정상
   - 홈 날씨 지도 아래 "지난 날씨" 가 어제 날짜까지
6. **하루 정상으로 돈 걸 확인한 뒤** 데이터 담당 PC 의 수집기를 끈다 (그 전엔 양쪽이 같이 받아 빈 시간이 없게. 같은 키라 하루 호출이 두 배지만 한도 안)

- 원본을 옮기는 동안 잠시 멈추고 싶으면 볼륨에 `HOLD` 파일: `docker compose exec weather-collector touch data/HOLD` (풀 때 `rm data/HOLD`)
- **키 오류**가 나면 수집기가 `data/STOP_<키이름>` 을 만들고 그 키 수집을 멈춥니다. 키를 고친 뒤
  `docker compose exec weather-collector rm data/STOP_DATA_GO_KR_KEY` (또는 `STOP_KMA_APIHUB_KEY`)
- **절대 `docker compose down -v` 금지** — `weatherraw` 볼륨(다시 못 받는 예보 원본)이 지워집니다
- 백업: `docker cp nong-clock-weather-collector:/app/collector/weather/data/raw/fcst .\weather-backup\fcst`

손으로 CSV 를 넣어 화면만 먼저 볼 때(수집기 없이): 데이터 담당 CSV 를 `C:\farmbid\collector\weather_site\input\` 에 넣으면 5분 안에 반영됩니다. 수집기 표가 생기면 더 최근 파일을 씁니다.

## 2. 접속

### 같은 곳 (학원·학교 내부망)

1. 서버에서 `ipconfig` → IPv4 주소 (예: `192.168.0.25`)
2. 방화벽 열기 — **관리자 PowerShell** 에서 한 번:
   ```powershell
   New-NetFirewallRule -DisplayName "FarmBid web" -Direction Inbound -Protocol TCP -LocalPort 80 `
     -RemoteAddress LocalSubnet,100.64.0.0/10 -Action Allow
   ```
   (내부망과 Tailscale 에서만 허용. 공유기 포트 포워딩은 하지 않습니다)
3. 내 PC 브라우저에서 `http://192.168.0.25`

### 집에서 (Tailscale)

포트를 인터넷에 열지 않고, 팀 컴퓨터끼리만 연결되는 무료 VPN 입니다.

1. [Tailscale](https://tailscale.com/download) 을 **서버와 내 PC 둘 다** 설치하고 같은 계정으로 로그인 (팀원은 서버 주인이 Tailscale 관리 화면에서 초대)
2. 서버 컴퓨터 이름 확인: Tailscale 아이콘 → 서버 이름 (예: `farmbid-server`) 또는 `100.x.y.z` 주소
3. 내 PC 브라우저에서 `http://farmbid-server` (또는 `http://100.x.y.z`)

## 3. 내 PC 에서 개발할 때 서버 데이터 쓰기

`frontend\.env` 에 서버 주소를 넣으면 `npm run dev` 화면이 서버에 모인 뉴스·ML API 를 씁니다 (내 PC 에서 수집기를 돌릴 필요 없음).

```
VITE_NEWS_URL=http://서버주소/data/news-recent.json
VITE_ML_API_BASE=http://서버주소/ml
```

화면 왼쪽 아래에 `테스트 모드 · 뉴스 서버 수집` 이 보이면 연결된 것입니다.

## 4. 고친 코드가 서버에 반영되는 흐름

1. 내 PC 에서 브랜치 → 커밋 → push → PR
2. PR 이 **main 에 합쳐지면** 10분 안에 서버가 받아서 바뀐 서비스만 다시 빌드
3. 확인: 관리자 화면 오른쪽 위 **배포 커밋 번호** (관리자 › 대시보드 › 서버·API 상태에 커밋 메시지·시각), 또는 서버의 `deploy\deploy.log`

바로 반영하고 싶으면 서버에서 `powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1`.

## 5. 자주 쓰는 명령 (서버, `C:\farmbid` 에서)

```powershell
docker compose ps                         # 서비스 상태
docker compose logs -f news-collector     # 뉴스 수집 기록 (Ctrl+C 로 나가기)
docker compose restart news-collector     # 수집기 다시 시작 (곧바로 한 번 수집)
docker compose exec news-collector python collect_news.py --relabel   # 규칙 바꾼 뒤 저장된 기사에 다시 적용
docker cp nong-clock-news-collector:/app/collector/news/data .\news-backup   # 수집한 뉴스 백업
```

## 문제 해결

| 증상 | 확인 |
|---|---|
| 서버 화면이 안 열림 | Docker Desktop 이 켜져 있는지, `docker compose ps` 에서 `web` 이 running 인지 |
| 내 PC 에서만 안 열림 | 방화벽 규칙(2번), 같은 내부망인지 / Tailscale 이 둘 다 연결됐는지 |
| 80 번을 다른 프로그램이 씀 | `.env` 의 `WEB_PORT=8080` → `deploy.ps1 -Force` → `http://서버주소:8080` |
| 날씨 수집 멈춤·실패 | 관리자 › 데이터 수집의 날씨 줄 상태 (오류 표시), `docker compose logs --tail 50 weather-collector`, 키 오류면 1-1의 STOP 파일 |
| 지난 날씨가 안 보임 | `docker compose logs --tail 20 weather-export` (전처리 결과 CSV 가 아직 없으면 "입력 파일이 없어요") |
| 뉴스가 안 쌓임 | 관리자 › 데이터 수집 › 뉴스 수집 (오류·해결 방법 표시) 또는 `http://서버주소/data/collect_log.json` 의 `errors` (키 오류면 `.env` 의 NAVER 값 확인 후 `docker compose up -d news-collector`) |
| 자동 배포가 안 됨 | `deploy\deploy.log` 에 "직접 고친 파일" → 서버에서 `git status` 확인 후 `git checkout -- .` 로 되돌림 |
