# Frontend (React + Vite)

팜비드 웹 화면. 시세·경매·회원 기능은 Spring API가 생기기 전까지 **가짜 데이터**로 동작하고, AI 예측은 **ML API(FastAPI)에 실제로 연결**됩니다.

## 실행

```powershell
cd frontend
npm install        # 처음 한 번
npm run dev        # 사용자 사이트 http://localhost:5173  ·  관리자 사이트 http://localhost:5173/admin/
```

- ML API도 같이 켜면 AI 예측이 실제 API 응답으로 나옵니다: `cd ml-api` → `python -m uvicorn app.main:app --reload`
- ML API가 꺼져 있으면 화면 위에 "데모 데이터" 안내가 뜨고 가짜 예측으로 대신 보여줍니다.
- API 주소를 바꾸려면 `.env.example`을 `.env`로 복사해서 `VITE_ML_API_BASE`를 고칩니다.

## 테스트 모드 (날씨·뉴스 실제 데이터)

Spring·DB 가 생기기 전에 **내 PC에서만** 기상청·네이버 실제 데이터로 화면을 확인하는 모드입니다.

1. `frontend/.env.example` 아래쪽을 `frontend/.env` 에 복사해 주석(`#`)을 풀고 키를 채웁니다
   - `DATA_GO_KR_KEY`: 공공데이터포털 일반 인증키(Decoding). 기상청 단기예보·기상특보 활용신청 필요
   - `NAVER_CLIENT_ID` · `NAVER_CLIENT_SECRET`: **NAVER API HUB**(네이버클라우드 콘솔) Application 의 Client ID · Client Secret, 검색(뉴스) API 선택. 네이버 개발자센터 검색 API 는 2026-07-31 에 신규 신청이 끝났습니다
2. `npm run dev` 를 다시 실행 → 화면 왼쪽 아래에 보라색 **테스트 모드** 표시

| 화면 | 실제로 바뀌는 것 |
|---|---|
| 홈 날씨 지도 | 시·도 17곳 기온·최저/최고·강수확률·습도·풍속 (단기예보), 특보 (기상특보). 지온은 아직 없음(—) |
| 홈 뉴스·농업 뉴스·검색의 뉴스 | 네이버 뉴스 검색 결과 (농산물 가격·수급 + 품목 16개), 품목·분류 태그는 `utils/itemMatch.js`·`mocks/news.js` 규칙 |

- 키는 `VITE_` 없이 적어서 **브라우저에 전달되지 않습니다.** Vite 개발 서버가 `/live/...` 요청에 키를 붙여 대신 보냅니다 (`vite.config.js`)
- 받은 데이터는 10분간 다시 쓰고, 그 뒤 화면을 열면 새로 받습니다 (뉴스 18회·날씨 35회 호출)
- **임시 구조입니다.** 실제 서비스는 수집기 → DB → Spring API → 화면. 빌드한 배포본은 항상 가짜 데이터(mock)로 동작합니다
- 시세·경매·회원은 테스트 모드에서도 가짜 데이터입니다
- **뉴스 거르기 규칙:** 단어 목록·기준 점수는 저장소 맨 위 `shared/news_rules.json` (뉴스 수집기 `collector/news` 와 같이 씀). 찾는 방식은 `utils/itemMatch.js`·`mocks/news.js`. 16개 품목 밖 작물(포도·샤인머스캣, 복숭아, 딸기, 마늘, 고추 등)은 링크 없는 회색 태그만 붙습니다 (검색 "포도" → 샤인머스캣 기사도 나옴)
- **서버에 모인 기사로 보기:** `frontend/.env` 에 `VITE_NEWS_URL=http://서버주소/data/news-recent.json` (서버 운영은 저장소 맨 위 `deploy/README.md`). 내 PC 의 `collector/news` 로 모은 기사는 테스트 모드(`live`)에서 자동으로 읽습니다
- **규칙 다듬기용 표본:** 테스트 모드로 `npm run dev` 를 켜 둔 채 `node scripts/news-sample.mjs` → `frontend/news-sample.json` (네이버 원본, 커밋 안 됨)

## 데모 계정 (로그인 화면에서 클릭하면 입력됨)

| 유형 | 이메일 | 비밀번호 |
|---|---|---|
| 일반회원 김구매 | user@farmbid.kr | user1234 |
| 일반회원 박농부 (농장명 있음) | farmer@farmbid.kr | farmer1234 |
| 관리자 (관리자 사이트) | admin@farmbid.kr | admin1234 |

회원가입·입찰·게시글·공지 결과는 브라우저(localStorage)에, 올린 사진은 브라우저 IndexedDB 에만 저장됩니다. 관리자 사이트의 **데모 데이터 초기화**로 되돌릴 수 있습니다.

## 화면

| 주소 | 화면 | 데이터 |
|---|---|---|
| `/` | 홈 (AI 예측, 오늘의 시세, 지역별 날씨 지도, 인기 경매) | 가짜 + ML API |
| `/market` | 시세·수급 (날짜·시장·품목 → 등급별 가격, 가격 추이, 출하지역별 가격, 반입 동향) | 가짜 |
| `/ai?item=&date=` | AI 가격예측 (내일 ~ 30일 뒤 날짜 선택) | **ML API** |
| `/auctions`, `/auctions/:id` | 경매 목록·상세(사진)·입찰·신고 | 가짜 |
| `/news?category=&item=&mine=1` | 농업 뉴스 (분류·품목·내 관심 품목 필터, 많이 나온 품목, 홈에는 헤드라인 6개) | 가짜 (실제: Spring 이 1시간마다 네이버 뉴스 검색 API 수집) |
| `/search?q=&tab=` | 통합 검색: 품목(시세·2주 예측)·경매·뉴스·게시판·공지 한 번에, 탭별 전체 보기. 헤더 검색창 자동완성 | 가짜 + ML API |
| `/board`, `/board/:id`, `/board/write` | 게시판 (맨 위 공지 + 회원 글, 말머리·검색·페이지, 사진 첨부, 댓글·답글, 글·댓글 신고) | 가짜 |
| `/mypage` | 관심 품목·내 경매·입찰 참여·알림·신고 내역·내 정보 수정·탈퇴 (로그인 필요, 탭은 `?tab=`) | 가짜 |
| `/mypage/auctions/new` | 경매 등록 (관리자 외 모든 회원, 관리자 승인 후 노출) | 가짜 + AI 참고가 |
| `/about` | 서비스 소개·가격 기준 안내(`#price-basis`)·만든 사람·문의처 (`pages/About.jsx` 위쪽 상수만 고치면 됨) | - |
| `/login`, `/signup` | 로그인·회원가입 (회원 유형 없음 — 모두 입찰·판매 가능) | 가짜 |
| **`/admin/*`** | **관리자 사이트 (별도 화면·별도 로그인)**: 대시보드, 신고·분쟁, 게시판 관리, 공지사항, 회원·경매 관리, 데이터 수집, 모델 성능 | ML API 상태는 실제, 나머지 가짜 |

### 관리자 사이트
- 사용자 사이트와 메뉴·로그인이 완전히 분리된 화면입니다 (`admin/index.html` → `src/admin/`). 관리자 계정만 들어갈 수 있습니다.
- 지금은 가짜 데이터를 같은 브라우저 저장소에서 공유해야 해서 같은 주소(`/admin/`)에 둡니다. Spring 이 생기면 다른 도메인(예: `admin.farmbid.kr`)에 따로 올려도 됩니다. 그때는 `.env` 의 `VITE_SITE_URL` 에 사용자 사이트 주소를 넣습니다.
- `npm run build` 하면 `dist/index.html`(사용자)과 `dist/admin/index.html`(관리자)이 따로 나옵니다. 배포 서버에는 `/admin/*` → `dist/admin/index.html`, 그 밖의 주소 → `dist/index.html` 규칙이 필요합니다 (개발 서버는 `vite.config.js` 가 처리).

## 구조와 규칙

```
src/
  api/        서버 호출. 화면은 반드시 여기 함수만 부른다
    client.js   API 주소 (한 곳에서만 관리), 데이터 출처(mock · live)
    live/       테스트 모드 전용: 기상청·네이버 응답 → 화면 모양 변환 (나중에 수집기·Spring 이 옮겨 쓸 규칙)
    ml.js       ML API — 실제 연결
    market.js · auction.js · auth.js · admin.js · board.js · notify.js · report.js · news.js · search.js   Spring 담당 — 지금은 mocks/ 반환
    upload.js   사진 업로드 (지금은 브라우저 IndexedDB, Spring 이 생기면 POST /api/uploads)
  mocks/      가짜 데이터 (Spring API가 생기면 지운다)
  components/ 공통 부품 (레이아웃, 가격 변동 표시, 로딩·에러 처리)
  pages/      사용자 사이트 화면
  admin/      관리자 사이트 (main.jsx 진입점, AdminApp.jsx 메뉴·로그인, pages/ 화면)
  utils/format.js  가격(원/kg)·날짜 표시
  utils/itemMatch.js  글에서 품목 찾기 (품목 별칭·한 글자 품목 규칙) — 통합 검색과 뉴스 품목 태그가 같이 씀
```

- **Spring API 연결 방법:** `api/market.js` 등의 함수 안쪽만 `request(주소, "/api/...")` 로 바꾸면 됩니다. 화면 코드는 고칠 필요 없습니다. 응답 모양은 `docs/06_api_spec.md` 2번 섹션의 제안을 따릅니다.
- **농업 뉴스:** 기사 제목·요약만 보여주고 누르면 언론사 원문이 새 탭으로 열린다 (본문은 옮기지 않음). 지금 기사는 화면 확인용 예시(링크는 example.com). 네이버 API 키는 서버에만 두므로 화면이 네이버를 직접 부르지 않는다 (명세 2-14). 테스트 모드에서만 Vite 개발 서버가 대신 부른다
- **품목 사진:** `src/assets/items/<품목코드>.png` 처럼 넣으면 자동으로 쓰입니다 (없으면 이모지). 규칙은 그 폴더의 `README.md`.
- **디자인:** 사용자 사이트는 A안(산뜻한 마켓형) — 색·모서리 값은 `styles.css` 맨 위 변수. 관리자 사이트는 `src/admin/admin.css` 에서 이전 색을 따로 고정.
- **품목·기간·지역은 하드코딩하지 않는다:** `GET /items`, `/horizons`, `/regions` 로 받아서 그립니다. 지역이 1개면 선택 박스를 숨깁니다.
- **가격 표기:** 모두 원/kg, 변동은 `▲ 80원 (+6.9%) 10/16(금) 대비` 처럼 비교 날짜를 함께 (`components/common.jsx` 의 `PriceChange`).
- ⚠️ 로그인·입찰 규칙 검사는 지금 프론트에서 흉내만 냅니다. 실제 검사는 반드시 Spring(서버)에서 해야 합니다.
