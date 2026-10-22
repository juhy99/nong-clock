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
| `web` → `/ml/` | ML API 중계 | `/ml/items` |
| `news-collector` | 켜자마자 한 번, 그 뒤 1시간마다 뉴스 수집 | — |
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
| 뉴스가 안 쌓임 | 관리자 › 데이터 수집 › 뉴스 수집 (오류·해결 방법 표시) 또는 `http://서버주소/data/collect_log.json` 의 `errors` (키 오류면 `.env` 의 NAVER 값 확인 후 `docker compose up -d news-collector`) |
| 자동 배포가 안 됨 | `deploy\deploy.log` 에 "직접 고친 파일" → 서버에서 `git status` 확인 후 `git checkout -- .` 로 되돌림 |
