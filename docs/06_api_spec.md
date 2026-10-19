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

| 값(일) | 화면 이름 |
|---|---|
| `7` | 1주 |
| `14` | 2주 |
| `30` | 1개월 |

- **프론트 규칙:** 기간 버튼은 `GET /horizons` 로 받아 그립니다. 기간이 바뀌어도 화면 코드를 고칠 필요가 없습니다.
- 그 외 값을 보내면 `422` 입니다.

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
| GET | `/regions` | 지역 목록 (현재 전국만) | AI 가격예측 › 지역 선택 (1개면 숨김) |
| GET | `/horizons` | 예측 기간 목록 | AI 가격예측 › 기간 버튼 |
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
| `horizon` | number | O | 예측 기간(일). **`GET /horizons` 의 `days` 값 중 하나** (현재 7, 14, 30) |

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

**에러**: 없는 `item`·`region` → `404`, `horizon`이 7/14/30이 아님 → `422`

---

### 1-5. `GET /predict/top-movers` 급등락 예상 품목

홈 화면 "AI 추천 · 급등락 예상 품목" 카드에 씁니다. 변동률이 **크게 움직이는 순서**(상승·하락 모두, 절댓값 기준)로 정렬됩니다.

**쿼리 파라미터** (모두 생략 가능)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `horizon` | `7` | 예측 기간 (`GET /horizons` 참고) |
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

## 2. Backend (Spring Boot)

> Spring 담당자가 작성해주세요. 화면 기준으로 필요한 API 후보입니다.

| 화면 | 필요한 데이터 | 주소 (예정) |
|---|---|---|
| 홈 › 상단 시세 띠, 오늘의 주요 시세 | 품목별 오늘 도매가(원/kg), **직전 조사일 대비 금액·%와 비교 날짜** | |
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
| 2026-10-19 | 예측 기간 1주/2주/1개월 확정 및 `GET /horizons` 추가, 지역은 전국만 제공(지역별은 설정으로 켜기) | |
| 2026-10-19 | 지역에 `national`(전국) 추가 및 기본값으로 지정, `region` 생략 가능 | |
| 2026-10-19 | 가격 단위 원/kg 통일, 품목 16개로 변경(`cabbage`=양배추), `/items`에 `emoji` 추가, 가격 비교 기준 명시 | |
