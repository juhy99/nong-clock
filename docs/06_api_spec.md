# API 명세서

> 팜비드(FarmBid) 서비스의 서버 API 명세입니다.
> **공유 파일**이므로 수정 전에 단톡방에 알려주세요.

| 서버 | 담당 | 로컬 주소 | 자동 문서 |
|---|---|---|---|
| ML API (FastAPI) | AI 가격예측 | `http://localhost:8000` | `http://localhost:8000/docs` |
| Backend (Spring Boot) | 시세·경매·회원 | 미정 | 미정 |

---

## 0. 공통 규칙

### 데이터 형식
- 요청·응답 모두 **JSON**, 글자는 UTF-8
- 날짜: `YYYY-MM-DD` 문자열 (예: `"2026-10-15"`)
- 가격: **모든 품목 1kg당 원 단위 정수** (예: `1240` = 1,240원/kg). 응답의 `unit` 은 항상 `"kg"`
  - 상자 단위 원본 가격은 상자 무게로 나눠 저장한다 (예: 배추 10kg 12,400원 → `1240`)
- 가격 비교(전일 대비 등)는 **직전 조사일 대비**이며, 비교 날짜를 함께 표기한다
  - KAMIS 가격은 평일 하루 1회 조사(토·일·공휴일 없음) → 월요일 시세는 금요일 대비
  - 화면 예: `▲ 80원 (+6.9%) 10/16(금) 대비`
- 퍼센트: 소수 첫째 자리까지 숫자 (예: `23.1` = 23.1%, 하락이면 음수 `-5.5`)

### 품목 코드 (`item`)
URL과 API 모두 아래 영어 코드를 씁니다. (예: 프론트 주소 `/market?item=napa_cabbage`) 단위는 전부 `kg` 입니다.

| 코드 | 이름 | 분류 |
|---|---|---|
| `potato` | 🥔 감자 | 근채류 |
| `onion` | 🧅 양파 | 조미채소 |
| `carrot` | 🥕 당근 | 근채류 |
| `apple` | 🍎 사과 | 과일류 |
| `watermelon` | 🍉 수박 | 과채류 |
| `napa_cabbage` | 🥬 배추 | 엽채류 |
| `radish` | 🌱 무 | 근채류 |
| `tomato` | 🍅 토마토 | 과채류 |
| `cabbage` | 🥗 양배추 | 엽채류 |
| `sweet_potato` | 🍠 고구마 | 근채류 |
| `button_mushroom` | 🍄 양송이 | 버섯류 |
| `pear` | 🍐 배 | 과일류 |
| `king_oyster_mushroom` | 🍄 새송이 | 버섯류 |
| `green_onion` | 🌿 대파 | 조미채소 |
| `mandarin` | 🍊 감귤 | 과일류 |
| `enoki_mushroom` | 🍄 팽이버섯 | 버섯류 |

> ⚠️ 이전 버전에서 `cabbage` 는 배추였지만, 지금은 **`cabbage` = 양배추, `napa_cabbage` = 배추** 입니다.
> 프론트는 품목 목록을 하드코딩하지 말고 `GET /items` 로 받아 쓰면 품목이 늘거나 줄어도 화면 코드를 고칠 필요가 없습니다.

> 정의 위치: `ml-api/app/core/catalog.py`. 품목을 추가·변경하면 이 표도 같이 고쳐주세요.

### 지역 코드 (`region`)

**현재는 `national`(전국) 예측만 제공합니다.** `region` 은 생략하면 `national` 입니다.

| 코드 | 이름 | 상태 |
|---|---|---|
| `national` | 전국 | ✅ 사용 중 (기본값) |
| `gyeonggi` 경기 · `gangwon` 강원 · `chungbuk` 충북 · `chungnam` 충남 · `jeonbuk` 전북 · `jeonnam` 전남 · `gyeongbuk` 경북 · `gyeongnam` 경남 · `jeju` 제주 | | ⏸ 예정 (지역별 모델 준비 후) |

- 지역별 예측은 ML API 환경변수 `ENABLE_REGIONAL_FORECAST=true` 로 켭니다. 켜면 `GET /regions` 에 위 9개 지역이 추가되고, 요청·응답 형식은 그대로입니다.
- 꺼져 있을 때 `national` 외 코드를 보내면 `404` 입니다.
- **프론트 규칙:** 지역 선택 박스는 `GET /regions` 로 채우고, **결과가 1개뿐이면 숨깁니다.** → 지금은 숨겨지고, 지역별 예측을 켜면 코드 수정 없이 나타납니다.

### 예측 기간 (`horizon`)

- **오늘(기준일)로부터 며칠 뒤까지 예측할지, `1` ~ `30` 중 아무 정수.** 화면에서 사용자가 날짜를 고르면 `고른 날짜 - 오늘` 일수를 보냅니다.
- `GET /horizons` 의 `7`(1주) · `14`(2주) · `30`(1개월)은 **빠른 선택 버튼**용이고, 이 중 가장 큰 값이 고를 수 있는 최대 날짜입니다.
- 0 이하나 31 이상을 보내면 `422` 입니다.
- ⚠️ **모델 담당 확인 필요:** 1~30일 **매일**의 예측값이 필요합니다 (7·14·30일만 예측하는 모델이면 사이 날짜를 어떻게 채울지 정해야 함).

### 에러 응답

| 상태 코드 | 의미 | 예시 |
|---|---|---|
| `404` | 없는 품목·지역 코드 | `{"detail": "unknown item: banana"}` |
| `422` | 요청 형식이 틀림 (빠진 값, 허용 안 되는 값) | 아래 참고 |

```json
// 422 예시: horizon 에 31 을 보낸 경우
{
  "detail": [
    { "type": "less_than_equal", "loc": ["body", "horizon"],
      "msg": "Input should be less than or equal to 30", "input": 31 }
  ]
}
```

---

## 1. ML API (FastAPI)

> ⚠️ **현재는 더미(가짜) 예측값**을 돌려줍니다. 응답 **형식은 최종과 동일**하므로 이 형식대로 화면·연동을 개발하면 됩니다.
> 같은 품목·지역·날짜로 요청하면 항상 같은 값이 나옵니다.

### 한눈에 보기

| 메서드 | 주소 | 설명 | 사용 화면 |
|---|---|---|---|
| GET | `/health` | 서버 상태 확인 | - |
| GET | `/items` | 품목 목록 | AI 가격예측 › 품종 선택 |
| GET | `/regions` | 지역 목록 (현재 전국만) | AI 가격예측 › 지역 선택 (1개면 숨김) |
| GET | `/horizons` | 빠른 선택 기간 (최대 30일) | AI 가격예측 › 날짜 선택 옆 버튼, 홈 기간 버튼 |
| POST | `/predict` | 가격 예측 | AI 가격예측 (`/ai`) |
| GET | `/predict/top-movers` | 급등락 예상 품목 | 홈 › AI 추천 · 급등락 예상 품목 |

---

### 1-1. `GET /health` 서버 상태

**응답 200**
```json
{ "status": "ok", "model_version": "dummy-0.1" }
```

---

### 1-2. `GET /items` 품목 목록

**응답 200**
```json
[
  { "code": "potato", "name": "감자", "unit": "kg", "category": "근채류", "emoji": "🥔" },
  { "code": "onion",  "name": "양파", "unit": "kg", "category": "조미채소", "emoji": "🧅" }
]
```

### 1-3. `GET /regions` 지역 목록

**응답 200**
```json
[
  { "code": "national", "name": "전국" }
]
```
지역별 예측을 켜면 `{ "code": "gyeonggi", "name": "경기" }` … 9개가 뒤에 추가됩니다.

### 1-3-1. `GET /horizons` 예측 기간 목록

**응답 200**
```json
[
  { "days": 7,  "label": "1주" },
  { "days": 14, "label": "2주" },
  { "days": 30, "label": "1개월" }
]
```

---

### 1-4. `POST /predict` 가격 예측

AI 가격예측 화면에서 품종·지역·예측 시점을 고르면 호출합니다.

**요청 본문**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `item` | string | O | 품목 코드 |
| `region` | string | X | 지역 코드. **생략하면 `national`(전국)** |
| `horizon` | number | O | 예측 기간(일). **1 ~ 30 중 아무 값** (화면에서 고른 날짜 - 오늘) |

```json
{ "item": "napa_cabbage", "horizon": 14 }
// 지역별 예측을 켠 뒤: { "item": "napa_cabbage", "region": "gyeonggi", "horizon": 14 }
```

**응답 200**

| 필드 | 타입 | 설명 | 화면 위치 |
|---|---|---|---|
| `item` / `item_name` / `unit` | string | 품목 코드 / 이름 / 단위(항상 `kg`) | |
| `region` | string | 지역 코드 (`national` = 전국) | |
| `horizon` | number | 요청한 예측 기간 | |
| `base_date` | string | 기준일 (오늘) | 그래프 실제↔예측 경계 |
| `base_price` | number | 기준일 도매가 (원/kg) | |
| `history` | 배열 | 최근 실제 시세 `{date, price}` (기준일 포함 15일) | 그래프 검은 선 "실제" |
| `forecast` | 배열 | 예측 `{date, price, lower, upper}` — 기준일 다음 날부터 `horizon`일 | 초록 점선 "예측" + 초록 영역 "오차범위" |
| `predicted_price` | number | `horizon`일 후 예상 도매가 (= forecast 마지막 값) | "14일 후 예상 도매가" 금액 |
| `change_pct` | number | 기준가 대비 변동률 (%) | "▲ OO% vs 오늘" |
| `confidence` | number | 신뢰도 지수 (0~100) | "신뢰도 지수 OO/100" |
| `alerts` | 배열 | 예측이 부정확해질 수 있는 이상기후 구간 (없으면 `[]`) | 주황 구간 + "예측이 깨지는 구간 분석" |
| `model_version` | string | 사용한 모델 버전 | |

`alerts` 항목

| 필드 | 타입 | 설명 |
|---|---|---|
| `start` / `end` | string | 구간 시작·끝 날짜 |
| `reason` | string | 원인 설명 문구 |
| `mape_normal` | number | 평상시 모델 평균 오차율 (%) |
| `mape_anomaly` | number | 비슷한 이상기후 때의 평균 오차율 (%) |

```json
{
  "item": "napa_cabbage",
  "item_name": "배추",
  "unit": "kg",
  "region": "national",
  "horizon": 14,
  "base_date": "2026-10-19",
  "base_price": 800,
  "history": [
    { "date": "2026-10-05", "price": 689 },
    { "date": "2026-10-06", "price": 691 },
    "... (중략) ...",
    { "date": "2026-10-19", "price": 800 }
  ],
  "forecast": [
    { "date": "2026-10-20", "price": 790, "lower": 766, "upper": 814 },
    { "date": "2026-10-21", "price": 782, "lower": 749, "upper": 816 },
    "... (중략) ...",
    { "date": "2026-11-02", "price": 722, "lower": 641, "upper": 803 }
  ],
  "predicted_price": 722,
  "change_pct": -9.8,
  "confidence": 79,
  "alerts": [
    {
      "start": "2026-10-26",
      "end": "2026-10-28",
      "reason": "[더미] 기온 편차 +2.4σ, 강수량 평년 대비 180% 예상",
      "mape_normal": 6.2,
      "mape_anomaly": 19.8
    }
  ],
  "model_version": "dummy-0.1"
}
```

**에러**: 없는 `item`·`region` → `404`, `horizon`이 1~30 밖 → `422`

---

### 1-5. `GET /predict/top-movers` 급등락 예상 품목

홈 화면 "AI 추천 · 급등락 예상 품목" 카드에 씁니다. 변동률이 **크게 움직이는 순서**(상승·하락 모두, 절댓값 기준)로 정렬됩니다.

**쿼리 파라미터** (모두 생략 가능)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `horizon` | `7` | 예측 기간 1~30일 |
| `limit` | `4` | 몇 개 받을지 (1~품목 수) |
| `region` | `national` | 지역 코드 (생략하면 전국) |

예) `GET /predict/top-movers?horizon=7&limit=4`

**응답 200**
```json
[
  { "item": "green_onion", "item_name": "대파", "unit": "kg",
    "predicted_price": 1608, "change_pct": 9.4, "confidence": 85 },
  { "item": "pear", "item_name": "배", "unit": "kg",
    "predicted_price": 2339, "change_pct": -7.9, "confidence": 88 }
]
```

| 필드 | 화면 위치 |
|---|---|
| `item_name` | 카드 제목 (예: "배추") |
| `change_pct` | "▲ 18.1%" (음수면 ▼) |
| `predicted_price` | "7일 후 예상 OO원/kg" |
| `confidence` | "AI 신뢰도 88%" |

---

## 2. Backend (Spring Boot) — 프론트 기준 제안

> **아직 Spring 담당자가 확정하지 않은 "제안"입니다.** 프론트(`frontend/`)는 지금 이 모양의 가짜 데이터(`frontend/src/mocks/`)로 동작합니다.
> Spring 이 이 모양대로 응답하면 프론트는 `frontend/src/api/*.js` 함수 안쪽만 바꾸면 됩니다. 주소·필드를 바꾸고 싶으면 이 문서를 고치고 단톡방에 알려주세요.
> 공통: 가격은 원/kg 정수, 날짜는 `YYYY-MM-DD`, 일시는 ISO 8601 (`2026-10-19T14:03:00+09:00`).

### 한눈에 보기

| 메서드 | 주소 (제안) | 설명 | 사용 화면 | 프론트 함수 |
|---|---|---|---|---|
| GET | `/api/prices/today` | 오늘 시세 + 직전 조사일 대비 | 홈 시세 띠·카드, 시세 표 | `getTodayPrices` |
| GET | `/api/prices/{item}/history?days=30` | 최근 N 조사일 도매·소매 | 시세 › 가격 동향 | `getPriceHistory` |
| GET | `/api/prices/{item}/markets` | 시장별 가격 | 시세 › 유통처별 비교 | `getMarketCompare` |
| GET | `/api/supply/{item}` | 월별 생산량 vs 평년 | 시세 › 수급 리포트 | `getSupply` |
| GET | `/api/weather/regions` | 시·도 17곳 오늘 날씨 + 특보 | 홈 날씨 지도 | `getRegionalWeather` |
| POST | `/api/uploads` (multipart, `files` 여러 개) | 사진 업로드 → 사진 주소 목록 | 경매 등록, 게시판 글쓰기 | `uploadImages` |
| GET | `/api/posts?category=&q=&page=` | 게시글 목록 (숨김 제외, 15개씩) | 게시판 | `getPosts` |
| GET | `/api/posts/{id}` | 게시글 보기 (조회수 +1) | 게시판 › 글 | `getPost` |
| POST · PUT · DELETE | `/api/posts` · `/api/posts/{id}` | 글쓰기·수정·삭제 (작성자 본인만) | 게시판 › 글쓰기 | `createPost` · `updatePost` · `deletePost` |
| GET | `/api/admin/posts` | 전체 글 (숨김 포함) | 관리자 › 게시판 관리 | `getAllPosts` |
| PATCH · DELETE | `/api/admin/posts/{id}` `{ "hidden", "reason" }` | 숨김·다시 보이기·삭제 (작성자에게 알림) | 관리자 › 게시판 관리 | `setPostHidden` · `adminDeletePost` |
| GET | `/api/posts/{id}/comments` | 댓글·답글 (답글은 `replies` 안에) | 게시판 › 글 | `getComments` |
| POST | `/api/posts/{id}/comments` `{ "body", "parent_id" }` | 댓글·답글 쓰기 (글쓴이·원댓글 작성자에게 알림) | 게시판 › 글 | `createComment` |
| DELETE | `/api/comments/{id}` | 댓글 삭제 (작성자 본인, 관리자는 사유와 함께) | 게시판 › 글, 관리자 › 게시판 관리 | `deleteComment` |
| GET | `/api/admin/board-bans` | 게시판 이용 제한 중인 회원 | 관리자 › 게시판 관리 | `getBannedUsers` |
| POST · DELETE | `/api/admin/users/{id}/board-ban` `{ "days", "reason" }` | 게시판 이용 제한 걸기·풀기 (회원에게 알림) | 관리자 › 게시판 관리, 신고·분쟁 | `banUser` · `liftBan` |
| GET | `/api/auctions?sort=popular\|ending\|price` | 진행 중 경매 목록 | 홈 인기 경매, 경매 마켓 | `getAuctions` |
| GET | `/api/auctions/{id}` | 경매 상세 + 입찰 기록 | 경매 상세 | `getAuction` |
| POST | `/api/auctions/{id}/bids` `{ "amount": 240000 }` | 입찰 (로그인 필요) | 경매 상세 | `placeBid` |
| GET | `/api/me/bids` | 내 입찰 현황 | 마이페이지 | `getMyBids` |
| POST | `/api/auth/signup` · `/api/auth/login` | 회원가입·로그인 | 회원가입·로그인 | `signup` · `login` |
| GET | `/api/notices` | 공지 목록 (`show_on_home` 이면 홈 배너) | 홈 배너, 개발자 › 공지 | `getNotices` |
| GET · PATCH | `/api/me` | 내 정보 조회·수정 (이름·연락처·지역·농장명·관심 품목·알림 설정) | 마이페이지 › 내 정보 | `updateProfile` |
| POST | `/api/me/password` `{ "current", "next" }` | 비밀번호 변경 | 마이페이지 › 내 정보 | `changePassword` |
| DELETE | `/api/me` `{ "password" }` | 회원 탈퇴 (진행 중 경매·최고가 입찰 있으면 `409`) | 마이페이지 › 내 정보 | `withdraw` |
| GET | `/api/me/auctions` | 내가 등록한 경매 | 마이페이지 › 내 경매 | `getMyAuctions` |
| POST | `/api/auctions` | 경매 등록 (판매자만, `승인대기`로 생성) | 마이페이지 › 새 경매 등록 | `createAuction` |
| POST | `/api/auctions/{id}/cancel` | 내 경매 취소 (입찰 0건일 때만) | 마이페이지 › 내 경매 | `cancelMyAuction` |
| GET | `/api/me/notifications` | 내 알림 목록 | 종 아이콘, 마이페이지 › 알림 | `getNotifications` |
| GET | `/api/me/notifications/unread-count` | 안 읽은 알림 수 (30초마다 호출) | 종 아이콘 배지 | `getUnreadCount` |
| POST | `/api/me/notifications/read` `{ "id" }` (생략 시 전부) | 읽음 처리 | 종 아이콘, 마이페이지 › 알림 | `markRead` |
| POST | `/api/reports` | 경매·입찰자·게시글·댓글 신고 | 경매 상세, 게시판 › 🚨 신고 | `submitReport` |
| GET | `/api/me/reports` | 내 신고와 처리 결과 | 마이페이지 › 신고 내역 | `getMyReports` |
| PATCH | `/api/admin/reports/{id}` `{ "status", "memo", "notify_reporter" }` | 신고 처리 + 신고자에게 결과 알림 | 개발자 › 신고·분쟁 | `processReport` |
| POST | `/api/admin/auctions/{id}/bids/cancel` `{ "bid_ids", "reason" }` | 비정상 입찰 취소 → 현재가 재계산, 입찰자·판매자 알림 | 개발자 › 신고·분쟁, 회원·경매 관리 | `cancelBids` |
| | `/api/admin/...` | 공지·회원·경매 관리 (관리자만) | 개발자 페이지 | `api/admin.js` |

### 2-1. `GET /api/prices/today` 예시

```json
{
  "base_date": "2026-10-19",
  "compared_date": "2026-10-16",
  "market": "가락시장",
  "unit": "kg",
  "items": [
    { "item": "napa_cabbage", "name": "배추", "emoji": "🥬", "category": "엽채류",
      "price": 800, "prev_price": 814, "change": -14, "change_pct": -1.7,
      "retail_price": 1890, "margin_pct": 136 }
  ]
}
```
- `compared_date` 는 직전 조사일 (주말·공휴일 제외) → 화면에 "10/16(금) 대비" 로 표시
- 품목 코드·이름·이모지는 ML API `GET /items` 와 같은 값

### 2-2. 경매 목록 항목 예시 (`GET /api/auctions`)

```json
{ "id": 2, "title": "해남 월동배추 10kg × 20망 (산지직송)", "emoji": "🥬", "item": "napa_cabbage",
  "origin": "전남 해남", "weight_kg": 200, "start_price": 150000, "current_bid": 236000, "bid_count": 6,
  "ends_at": "2026-10-20T15:00:00+09:00", "seller": "seller1", "status": "진행중" }
```
- `status`: `승인대기` → (관리자 승인) → `진행중` → `마감` / `중단`
- 입찰 규칙(서버에서 검사): 로그인, 본인 상품 불가, 진행 중·마감 전, 최소 `현재가 + 1,000원` (첫 입찰은 시작가 이상)

### 2-3. 회원가입 요청 예시 (`POST /api/auth/signup`)

```json
{ "email": "farmer@farmbid.kr", "password": "abcd1234", "name": "박농부",
  "phone": "010-3333-4444", "region": "충남", "farm_name": "논산 햇살농장", "marketing": false }
```
- **회원 유형을 고르지 않음:** 모든 회원이 입찰도 판매(경매 등록)도 할 수 있음. 서버가 `type: "member"` 로 저장하고, 관리자(`admin`)는 DB에서 지정
- `farm_name`(농장·상호명)은 선택. 있으면 경매 판매자 이름으로 함께 표시
- 비밀번호: 영문+숫자 8자 이상, **서버에서 암호화 저장**

### 2-4. 알림 항목 예시 (`GET /api/me/notifications`)

```json
{ "id": 12, "type": "auction", "title": "입찰 상회", "body": "'해남 월동배추 10kg × 20망'에 더 높은 입찰(240,000원)이 들어왔어요.",
  "link": "/auctions/2", "read": false, "at": "2026-10-19T14:03:00+09:00" }
```
- `type`: `auction`(경매·입찰) / `comment`(내 글에 댓글·내 댓글에 답글) / `weather`(이상기후 주의) / `notice`(공지) / `report`(신고 처리 결과). 회원이 내 정보에서 종류별로 끌 수 있음 → Spring 이 알림을 만들 때 회원 설정을 확인
- 알림을 만드는 때: 새 입찰(판매자), 상회 입찰(직전 최고가 입찰자), 경매 승인·중단(판매자), 입찰 취소(입찰자·판매자), 신고 접수·처리(신고자), 공지 등록 시 "회원 전체에게 알림" 선택, 관심 품목 예측에 이상기후 구간(`alerts`)이 생길 때(배치)
- 화면은 30초마다 `unread-count` 를 물어보는 방식(폴링). 실시간 푸시는 필요해지면 추가

### 2-5. 신고 요청 예시 (`POST /api/reports`)

```json
// 경매
{ "kind": "auction", "target_id": 1, "type": "부정입찰", "bidder": "buyer3", "reason": "같은 사람이 여러 계정으로 입찰가를 올리는 것 같습니다." }
// 게시글 · 댓글
{ "kind": "comment", "target_id": 12, "post_id": 18, "type": "욕설·비방", "reason": "다른 회원에게 욕설을 했어요." }
```
- `kind`: `auction` / `post` / `comment`
- `type` — 경매: `허위매물` / `사기의심` / `부정입찰` / `기타`, 게시판: `욕설·비방` / `스팸·광고` / `개인정보 노출` / `허위 정보` / `기타`
- `bidder` 는 경매 부정입찰일 때만(선택). 회원 화면에는 가려진 아이디만 보여줌
- 서버가 신고 대상의 작성자(`target_user`)를 찾아 저장 → 관리자가 신고 화면에서 바로 글 숨김·댓글 삭제·작성자 이용 제한
- 내 글·댓글은 신고할 수 없고, 처리 중인 같은 대상을 다시 신고하면 `409`
- 상태: `접수` → `검토중` → `처리완료` / `반려`. 처리 메모는 신고자에게 그대로 보이므로 개인정보를 쓰지 않음

### 2-6. 경매 등록 요청 예시 (`POST /api/auctions`)

```json
{ "item": "potato", "title": "강원 수미감자 10kg × 3박스", "origin": "강원 평창", "weight_kg": 30,
  "start_price": 45000, "days": 3, "description": "오늘 수확한 수미감자입니다." }
```
- `item`: 16개 예측 품목 코드, 예측 품목이 아니면 `null`. **품질 등급은 받지 않음** (품질 분류 기준 없음)
- `days`: 1 / 3 / 5 / 7. 사진 업로드는 Spring 연결 때 추가
- 회원 탈퇴는 정보를 지우지 않고 `status: "탈퇴"` 로 바꿈 (지난 거래 기록 보존). 같은 이메일로 재가입 불가

### 2-7. 지역 날씨 예시 (`GET /api/weather/regions`)

```json
{ "base_time": "2026-10-19T05:00:00+09:00",
  "regions": [
    { "id": "gangwon", "name": "강원", "temp": 10, "min": 3, "max": 14, "icon": "☁️", "sky": "흐림",
      "rain_prob": 20, "humidity": 70, "wind": 3.4, "soil_temp": 9, "warning": "서리 주의보",
      "note": "일교차 큼 · 엽채류 냉해 주의" }
  ] }
```
- `id` 는 지도 데이터(`@svg-maps/south-korea`)의 지역 id: `seoul, busan, daegu, incheon, gwangju, daejeon, ulsan, sejong, gyeonggi, gangwon, north-chungcheong, south-chungcheong, north-jeolla, south-jeolla, north-gyeongsang, south-gyeongsang, jeju`
- `name` 은 회원 지역과 같은 이름 (로그인하면 내 지역을 먼저 보여줌). 데이터는 기상청 단기예보·기상특보를 시·도 대표 지점으로 모으는 것을 제안

### 2-8. 사진 업로드 (`POST /api/uploads`)
- `multipart/form-data`, 필드 이름 `files` (여러 장). JPG·PNG·WEBP·GIF, 장당 10MB 이하, 한 번에 5장까지
- 응답: `{ "urls": ["https://.../a1b2.jpg", ...] }` → 경매 등록 `images`, 게시글 `images` 에 그대로 넣음 (첫 번째가 대표 사진)
- 사진 파일은 서버 폴더나 S3 같은 저장소에, DB 에는 **주소만** 저장

### 2-9. 게시글 예시 (`GET /api/posts`)

```json
{ "rows": [ { "id": 18, "category": "정보", "title": "배추 가격 다음 주에 오를 것 같네요", "images": [],
              "author": "seller1", "author_name": "박농부", "created_at": "2026-10-19T15:01:00+09:00", "views": 132 } ],
  "total": 18, "page": 1, "pages": 2 }
```
- 말머리(`category`): `자유` / `질문` / `정보` / `거래후기`. 글쓰기 요청: `{ "category", "title"(2~80자), "body", "images" }`
- 목록 맨 위 공지는 `GET /api/notices` 를 그대로 사용 (관리자 › 공지사항에서 작성)
- 조회수는 같은 사람이 새로고침할 때마다 오르지 않게 서버에서 막는 것을 권장
- 목록 항목에 `comment_count`(지운 댓글 제외) 포함 → 제목 옆 `[3]`

### 2-10. 댓글 예시 (`GET /api/posts/{id}/comments`)

```json
[ { "id": 1, "parent_id": null, "author": "buyer1", "author_name": "김구매", "body": "저도 그래프 봤어요.",
    "created_at": "2026-10-19T15:40:00+09:00", "deleted": false,
    "replies": [ { "id": 2, "parent_id": 1, "author": "seller1", "author_name": "박농부", "body": "저는 1주 정도 보려고요.", "deleted": false } ] } ]
```
- 답글은 **1단계까지**. 답글에 답하면 같은 원댓글 아래에 붙음 (알림은 실제로 답한 댓글의 작성자에게)
- 댓글 1~500자. 답글이 달린 댓글을 지우면 `deleted: true` 로 남기고 내용은 비움("삭제된 댓글입니다")
- 알림: 내 글에 댓글 → 글쓴이, 내 댓글에 답글 → 원댓글 작성자 (본인이 쓴 건 알림 없음)

### 2-11. 게시판 이용 제한 (`POST /api/admin/users/{id}/board-ban`)

```json
{ "days": 7, "reason": "스팸 게시 반복" }   // days: 3 / 7 / 30 / null(영구)
```
- 제한 중에는 **글·댓글 작성만 막음** (로그인·입찰·판매는 가능). 계정 전체 정지는 기존 회원 관리의 "이용 정지"
- 글쓰기·댓글 API 는 제한 중이면 `403` + 남은 기간·사유. 걸 때·풀 때 회원에게 알림
- 회원 정보에 `board_ban: { until, reason, at }` 저장 (`until` 이 null 이면 영구)

### 2-12. 품목 대표 사진
- 시세 카드·품목 버튼에 쓰는 품목 사진은 **서버가 아니라 프론트 파일**로 둠: `frontend/src/assets/items/<품목코드>.png` (규칙은 같은 폴더의 README)
- 사진이 없는 품목은 이모지(`GET /items` 의 `emoji`)로 대신 보여줌

## 3. 정해야 할 것

- [ ] 프론트가 ML API를 **직접 호출**할지, **Spring을 거쳐** 호출할지
- [ ] 신뢰도 지수(`confidence`) 계산 방식 (예: 백테스트 오차율 기반)
- [ ] 예측을 **요청 때마다 계산**할지, **매일 미리 계산해 DB에 저장**할지
- [ ] 품목·지역 코드를 위 영어 코드로 확정할지 (KAMIS 품목코드와의 매핑 포함)
- [ ] 비정상 입찰 판단 기준 (지금은 관리자가 신고를 보고 직접 골라 취소. 입찰 IP 저장 여부)
- [ ] 새 DB 테이블: 관심 품목, 알림, 신고 (+ 입찰에 `cancelled`, 회원에 `status`·알림 설정)
- [ ] 새 DB 테이블: 게시글(숨김 여부·사유 포함), 사진 주소(경매·게시글 공용), 경매에 사진 목록
- [ ] 예측 모델이 1~30일 **매일** 값을 낼 수 있는지 (사용자가 아무 날짜나 고름)
- [ ] 관리자 사이트 배포 주소 (같은 도메인 `/admin/` 또는 `admin.` 서브도메인)
- [ ] 새 DB 테이블: 댓글(답글은 `parent_id`, `deleted`), 회원에 게시판 이용 제한(`board_ban_until`·사유), 신고에 `kind`·`target_user`
- [ ] 회원 유형 정리: `buyer`·`seller` 를 `member` 하나로 (이미 만든 테이블이 있으면 변경)

---

## 변경 이력

| 날짜 | 내용 | 작성자 |
|---|---|---|
| 2026-10-15 | 최초 작성 (ML API) | |
| 2026-10-19 | Spring API 제안(시세·경매·회원·공지) 추가 — 프론트 가짜 데이터 기준 | |
| 2026-10-19 | 예측 기간 1주/2주/1개월 확정 및 `GET /horizons` 추가, 지역은 전국만 제공(지역별은 설정으로 켜기) | |
| 2026-10-19 | 지역에 `national`(전국) 추가 및 기본값으로 지정, `region` 생략 가능 | |
| 2026-10-19 | 가격 단위 원/kg 통일, 품목 16개로 변경(`cabbage`=양배추), `/items`에 `emoji` 추가, 가격 비교 기준 명시 | |
| 2026-10-19 | Spring API 제안 추가: 내 정보 수정·탈퇴, 경매 등록·취소, 알림, 신고, 관리자 입찰 취소·신고 결과 알림 | |
| 2026-10-19 | 예측 기간 `horizon` 을 1~30일 아무 값으로 확장 (`/horizons` 는 빠른 선택용). Spring 제안 추가: 지역별 날씨, 사진 업로드, 게시판, 관리자 게시판 관리 | |
| 2026-10-20 | 회원 유형 선택 제거(모두 판매 가능), 댓글·답글, 게시글·댓글 신고, 게시판 이용 제한, 품목 대표 사진 규칙 추가 | |
