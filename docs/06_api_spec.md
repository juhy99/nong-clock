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
- 가격: **원 단위 정수** (예: `18200`)
- 퍼센트: 소수 첫째 자리까지 숫자 (예: `23.1` = 23.1%, 하락이면 음수 `-5.5`)

### 품목 코드 (`item`)
URL과 API 모두 아래 영어 코드를 씁니다. (프론트 주소 `/market?item=cabbage` 와 동일)

| 코드 | 이름 | 단위 | 분류 |
|---|---|---|---|
| `cabbage` | 배추 | 10kg | 엽채류 |
| `lettuce` | 상추 | 4kg | 엽채류 |
| `onion` | 양파 | 15kg | 조미채소 |
| `garlic` | 깐마늘 | 1kg | 조미채소 |
| `hot_pepper` | 청양고추 | 10kg | 과채류 |
| `tomato` | 토마토 | 5kg | 과채류 |
| `strawberry` | 딸기 | 2kg | 과일류 |
| `potato` | 감자 | 20kg | 근채류 |

> 정의 위치: `ml-api/app/core/catalog.py`. 품목을 추가·변경하면 이 표도 같이 고쳐주세요.

### 지역 코드 (`region`)

| 코드 | 이름 | 코드 | 이름 | 코드 | 이름 |
|---|---|---|---|---|---|
| `gyeonggi` | 경기 | `chungnam` | 충남 | `gyeongbuk` | 경북 |
| `gangwon` | 강원 | `jeonbuk` | 전북 | `gyeongnam` | 경남 |
| `chungbuk` | 충북 | `jeonnam` | 전남 | `jeju` | 제주 |

### 에러 응답

| 상태 코드 | 의미 | 예시 |
|---|---|---|
| `404` | 없는 품목·지역 코드 | `{"detail": "unknown item: banana"}` |
| `422` | 요청 형식이 틀림 (빠진 값, 허용 안 되는 값) | 아래 참고 |

```json
// 422 예시: horizon 에 10 을 보낸 경우
{
  "detail": [
    { "type": "literal_error", "loc": ["body", "horizon"],
      "msg": "Input should be 7, 14 or 30", "input": 10 }
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
| GET | `/regions` | 지역 목록 | AI 가격예측 › 재배 지역 선택 |
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
  { "code": "cabbage", "name": "배추", "unit": "10kg", "category": "엽채류" },
  { "code": "lettuce", "name": "상추", "unit": "4kg",  "category": "엽채류" }
]
```

### 1-3. `GET /regions` 지역 목록

**응답 200**
```json
[
  { "code": "gyeonggi", "name": "경기" },
  { "code": "gangwon",  "name": "강원" }
]
```

---

### 1-4. `POST /predict` 가격 예측

AI 가격예측 화면에서 품종·지역·예측 시점을 고르면 호출합니다.

**요청 본문**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `item` | string | O | 품목 코드 |
| `region` | string | O | 지역 코드 |
| `horizon` | number | O | 며칠 뒤까지 예측할지. **`7`, `14`, `30` 중 하나** |

```json
{ "item": "lettuce", "region": "gyeonggi", "horizon": 14 }
```

**응답 200**

| 필드 | 타입 | 설명 | 화면 위치 |
|---|---|---|---|
| `item` / `item_name` / `unit` | string | 품목 코드 / 이름 / 단위 | |
| `region` | string | 지역 코드 | |
| `horizon` | number | 요청한 예측 기간 | |
| `base_date` | string | 기준일 (오늘) | 그래프 실제↔예측 경계 |
| `base_price` | number | 기준일 도매가 | |
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
  "item": "lettuce",
  "item_name": "상추",
  "unit": "4kg",
  "region": "gyeonggi",
  "horizon": 14,
  "base_date": "2026-10-15",
  "base_price": 18200,
  "history": [
    { "date": "2026-10-01", "price": 16289 },
    { "date": "2026-10-02", "price": 16586 },
    "... (중략) ...",
    { "date": "2026-10-15", "price": 18200 }
  ],
  "forecast": [
    { "date": "2026-10-16", "price": 18325, "lower": 17776, "upper": 18875 },
    { "date": "2026-10-17", "price": 18351, "lower": 17572, "upper": 19130 },
    "... (중략) ...",
    { "date": "2026-10-29", "price": 19323, "lower": 17154, "upper": 21492 }
  ],
  "predicted_price": 19323,
  "change_pct": 6.2,
  "confidence": 84,
  "alerts": [
    {
      "start": "2026-10-22",
      "end": "2026-10-24",
      "reason": "[더미] 기온 편차 +2.4σ, 강수량 평년 대비 180% 예상",
      "mape_normal": 6.2,
      "mape_anomaly": 19.8
    }
  ],
  "model_version": "dummy-0.1"
}
```

**에러**: 없는 `item`·`region` → `404`, `horizon`이 7/14/30이 아님 → `422`

---

### 1-5. `GET /predict/top-movers` 급등락 예상 품목

홈 화면 "AI 추천 · 급등락 예상 품목" 카드에 씁니다. 변동률이 **크게 움직이는 순서**(상승·하락 모두, 절댓값 기준)로 정렬됩니다.

**쿼리 파라미터** (모두 생략 가능)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `horizon` | `7` | 며칠 뒤 기준 (`7`, `14`, `30`) |
| `limit` | `4` | 몇 개 받을지 (1~8) |
| `region` | `gyeonggi` | 지역 코드 |

예) `GET /predict/top-movers?horizon=7&limit=4`

**응답 200**
```json
[
  { "item": "hot_pepper", "item_name": "청양고추", "unit": "10kg",
    "predicted_price": 58763, "change_pct": 8.8, "confidence": 89 },
  { "item": "garlic", "item_name": "깐마늘", "unit": "1kg",
    "predicted_price": 10636, "change_pct": 8.5, "confidence": 84 }
]
```

| 필드 | 화면 위치 |
|---|---|
| `item_name` | 카드 제목 "상추" |
| `change_pct` | "▲ 18.1%" (음수면 ▼) |
| `predicted_price` | "7일 후 예상 21,501원" |
| `confidence` | "AI 신뢰도 88%" |

---

## 2. Backend (Spring Boot)

> Spring 담당자가 작성해주세요. 화면 기준으로 필요한 API 후보입니다.

| 화면 | 필요한 데이터 | 주소 (예정) |
|---|---|---|
| 홈 › 상단 시세 띠, 오늘의 주요 시세 | 품목별 오늘 중도매가, 전일 대비 | |
| 홈 › 실시간 농업 날씨, 기상특보 | 지역 날씨, 특보 문구 | |
| 홈 › 인기 경매 | 진행 중 경매 목록 | |
| 시세·수급 › 품목 표 | 중도매가, 전일 대비, 소매가, 유통마진 | |
| 시세·수급 › 가격 동향 그래프 | 최근 30일 도매/소매가 | |
| 시세·수급 › 유통처별 가격 | 시장별 가격 | |
| 시세·수급 › 수급 동향 리포트 | 월별 생산량, 평년값, 관측 문구 | |
| 경매 마켓 | 경매 목록·상세·입찰 | |
| 마이페이지 | 회원 정보, 입찰 내역 | |

---

## 3. 정해야 할 것

- [ ] 프론트가 ML API를 **직접 호출**할지, **Spring을 거쳐** 호출할지
- [ ] 신뢰도 지수(`confidence`) 계산 방식 (예: 백테스트 오차율 기반)
- [ ] 예측을 **요청 때마다 계산**할지, **매일 미리 계산해 DB에 저장**할지
- [ ] 품목·지역 코드를 위 영어 코드로 확정할지 (KAMIS 품목코드와의 매핑 포함)

---

## 변경 이력

| 날짜 | 내용 | 작성자 |
|---|---|---|
| 2026-10-15 | 최초 작성 (ML API) | |
