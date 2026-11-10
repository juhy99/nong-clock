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

### 가격 기준 (시장 · 등급)
- **따로 고르지 않는 가격은 모두 전국 도매시장 평균(`national`) · 상 등급(`HIGH`) · 원/kg** 이다
  - 홈 시세 띠·오늘의 주요 시세, 통합 검색 품목 요약, 마이페이지 관심 품목, 경매 등록 AI 참고가, 가격 알림
- **AI 예측(ML API)은 공영도매시장 경매 단가(원/kg)** = 그날 총 경락 금액 ÷ 총 물량 (등급을 나누지 않은 농가 수취 경락가, 107품목 모델의 정답). 도매시장 32곳별 (11/4 팀 결정). `market` 을 생략하면 전국
- **예측 오차·신뢰도는 모델 검증 결과** (`shared/model_accuracy.json`, 107품목 최종 앙상블 검증 기간 2025-07~ WAPE). 품목 평균: 1주 17.7% · 2주 20.5% · 1개월 22.9% · 3개월 24.7% · 6개월 26.8% (그날 가격 기준)
  - 시장별 모델은 아직 없어서 지금은 `시장별 가격 = 전국 예측 × 시장 계수` (`ml-api/app/core/markets.py`). 실제 시장별 모델이 붙으면 계수 자리만 바뀌고 API 형식은 그대로
- 시장·등급은 시세·수급 화면(`/market`)에서 고를 수 있다 (처음 열면 전국 · 상). AI 예측(`/ai`)은 시장을 고른다 (처음 열면 서울가락)
- 도매 등급 코드 = DB `price_daily.grade`: `SPECIAL`(특) · `HIGH`(상) · `MID`(중) · `LOW`(하) · `ALL`(평균, 거래량 반영)
- 소매가는 **전국 소매가 하나** (시장·등급 구분 없음)
- 품목은 107개이고 **품종은 나누지 않는다** (예: 무 = 가을무·고랭지무 모두 `radish`)
- 화면에는 기준을 군데군데 적지 않고, 서비스 소개 화면(`/about#price-basis`)에 모아서 안내한다

### 품목 코드 (`item`)
URL과 API 모두 아래 영어 코드를 씁니다. (예: 프론트 주소 `/market?item=napa_cabbage`) 단위는 전부 `kg` 입니다.

- **예측 품목은 50개** (11-11, `shared/items50.json`, 순서 = 물량 순위). `GET /items`·`POST /predict`·`GET /predict/top-movers` 는 이 50개만 다룬다. 50개 밖 품목(예: 양송이 `button_mushroom`, 석류)은 예측 `404`
- 품목 정보 표(`shared/items.json`)는 그대로 **107개** = 공영도매시장 거래 품목 (11/4 팀 회의, 모델 검증 결과도 107품목). 50개는 모두 이 안에 있다
- `code4` = **공영도매 품목코드(4자리)**. 모델 결과는 이 코드로 붙인다
- `category` = **공영 부류** (품목코드 앞 2자리: 03 두류 · 04 잡곡 · 05 서류 · 06 과일류 · 07 견과류 · 08·09 과채류 · 10 엽경채류 · 11 근채류 · 12 조미채소류 · 13 양채류 · 14 산채류 · 17 버섯류)
- 이모지가 없는 품목은 부류 기본 이모지 (두류 🫘 · 잡곡 🌽 · 서류 🥔 · 과일류 🍏 · 견과류 🌰 · 과채류 🫑 · 엽경채류 🥬 · 근채류 🥕 · 조미채소류 🧄 · 양채류 🥦 · 산채류 🌿 · 버섯류 🍄)
- 기존 16개 영어 코드(`napa_cabbage` 등)는 URL·다른 화면에서 쓰므로 **바꾸지 않았다**. 새 품목도 같은 방식의 영어 코드
- 상추(`lettuce`, 1005)는 잎상추(청상추·적상추·포기상추 합산), 양상추(`iceberg_lettuce`, 1301)는 결구상추 — **다른 품목**
- 이름은 화면 표시용으로 줄였다 (예: 브로콜리(녹색꽃양배추) → 브로콜리, 참다래(키위) → 키위)

> ⚠️ `cabbage` = 양배추, `napa_cabbage` = 배추 입니다.
> 프론트는 품목 목록을 하드코딩하지 말고 `GET /items` 로 받아 쓰면 품목이 늘거나 줄어도 화면 코드를 고칠 필요가 없습니다.

> 정의 위치: **`shared/items.json` 한 파일** (ml-api `app/core/catalog.py` 와 화면 `frontend/src/mocks/catalog.js` 가 같이 읽음). 가짜 시세·가짜 예측용 기준가 `base_price` 도 이 파일에 있고 **가짜 값**입니다.

<details><summary>품목 107개 전체 표 (펼치기)</summary>

| 코드 | 이름 | code4 | 부류 |
|---|---|---|---|
| `onion` | 🧅 양파 | `1201` | 조미채소류 |
| `radish` | 🌱 무 | `1101` | 근채류 |
| `napa_cabbage` | 🥬 배추 | `1001` | 엽경채류 |
| `apple` | 🍎 사과 | `0601` | 과일류 |
| `cucumber` | 🥒 오이 | `0901` | 과채류 |
| `watermelon` | 🍉 수박 | `0801` | 과채류 |
| `green_onion` | 🌿 대파 | `1202` | 조미채소류 |
| `cabbage` | 🥗 양배추 | `1004` | 엽경채류 |
| `potato` | 🥔 감자 | `0501` | 서류 |
| `mandarin` | 🍊 감귤 | `0614` | 과일류 |
| `squash` | 🎃 호박 | `0902` | 과채류 |
| `banana` | 🍌 바나나 | `0612` | 과일류 |
| `sweet_potato` | 🍠 고구마 | `0502` | 서류 |
| `carrot` | 🥕 당근 | `1103` | 근채류 |
| `tomato` | 🍅 토마토 | `0803` | 과채류 |
| `grape` | 🍇 포도 | `0603` | 과일류 |
| `young_napa_cabbage` | 🥬 얼갈이배추 | `1002` | 엽경채류 |
| `pear` | 🍐 배 | `0602` | 과일류 |
| `green_chili` | 🌶️ 풋고추 | `1205` | 조미채소류 |
| `korean_melon` | 🍈 참외 | `0802` | 과채류 |
| `peach` | 🍑 복숭아 | `0604` | 과일류 |
| `strawberry` | 🍓 딸기 | `0804` | 과채류 |
| `lettuce` | 🥬 상추 | `1005` | 엽경채류 |
| `cherry_tomato` | 🍅 방울토마토 | `0806` | 과채류 |
| `king_oyster_mushroom` | 🍄 새송이버섯 | `1711` | 버섯류 |
| `young_radish` | 🥬 열무 | `1006` | 엽경채류 |
| `chive` | 🥬 부추 | `1010` | 엽경채류 |
| `sweet_persimmon` | 🍏 단감 | `0605` | 과일류 |
| `spinach` | 🥬 시금치 | `1008` | 엽경채류 |
| `garlic` | 🧄 마늘 | `1209` | 조미채소류 |
| `eggplant` | 🍆 가지 | `0903` | 과채류 |
| `ponytail_radish` | 🥕 알타리무 | `1102` | 근채류 |
| `paprika` | 🫑 파프리카 | `1326` | 양채류 |
| `enoki_mushroom` | 🍄 팽이버섯 | `1705` | 버섯류 |
| `orange` | 🍊 오렌지 | `0618` | 과일류 |
| `iceberg_lettuce` | 🥦 양상추 | `1301` | 양채류 |
| `scallion` | 🧄 쪽파 | `1203` | 조미채소류 |
| `oyster_mushroom` | 🍄 느타리버섯 | `1701` | 버섯류 |
| `melon` | 🍈 멜론 | `0805` | 과채류 |
| `bok_choy` | 🥬 청경채 | `1031` | 엽경채류 |
| `broccoli` | 🥦 브로콜리 | `1306` | 양채류 |
| `perilla_leaf` | 🥬 깻잎 | `1011` | 엽경채류 |
| `water_parsley` | 🥬 미나리 | `1009` | 엽경채류 |
| `plum` | 🍏 자두 | `0608` | 과일류 |
| `corn` | 🌽 옥수수 | `0401` | 잡곡 |
| `astringent_persimmon` | 🍏 떫은감 | `0606` | 과일류 |
| `hybrid_citrus` | 🍊 만감 | `0615` | 과일류 |
| `shiitake` | 🍄 표고버섯 | `1704` | 버섯류 |
| `pineapple` | 🍍 파인애플 | `0613` | 과일류 |
| `shishito_pepper` | 🌶️ 꽈리고추 | `1206` | 조미채소류 |
| `bomdong` | 🥬 봄동배추 | `1003` | 엽경채류 |
| `bell_pepper` | 🫑 피망 | `1302` | 양채류 |
| `red_chili` | 🌶️ 홍고추 | `1208` | 조미채소류 |
| `bean_sprout` | 🥬 콩나물 | `1016` | 엽경채류 |
| `crown_daisy` | 🥬 쑥갓 | `1012` | 엽경채류 |
| `kiwi` | 🥝 키위 | `0611` | 과일류 |
| `mustard_leaf` | 🥬 갓 | `1013` | 엽경채류 |
| `red_cabbage` | 🥦 적채 | `1305` | 양채류 |
| `ginger` | 🫚 생강 | `1210` | 조미채소류 |
| `chicory` | 🥦 치커리 | `1303` | 양채류 |
| `chamnamul` | 🌿 참나물 | `1406` | 산채류 |
| `kohlrabi` | 🥦 콜라비 | `1314` | 양채류 |
| `mung_bean_sprout` | 🥬 숙주나물 | `1017` | 엽경채류 |
| `chard` | 🥬 근대 | `1014` | 엽경채류 |
| `beet` | 🥦 비트 | `1311` | 양채류 |
| `celery` | 🥦 셀러리 | `1304` | 양채류 |
| `lemon` | 🍋 레몬 | `0617` | 과일류 |
| `mango` | 🥭 망고 | `0636` | 과일류 |
| `mallow` | 🥬 아욱 | `1015` | 엽경채류 |
| `chwinamul` | 🌿 취나물 | `1401` | 산채류 |
| `button_mushroom` | 🍄 양송이 | `1702` | 버섯류 |
| `lotus_root` | 🥕 연근 | `1105` | 근채류 |
| `sweet_potato_stem` | 🥬 고구마순 | `1019` | 엽경채류 |
| `romaine` | 🥦 로메인 | `1328` | 양채류 |
| `thin_scallion` | 🧄 실파 | `1204` | 조미채소류 |
| `cherry` | 🍒 체리 | `0657` | 과일류 |
| `fig` | 🍏 무화과 | `0627` | 과일류 |
| `kale` | 🥦 케일 | `1307` | 양채류 |
| `beech_mushroom` | 🍄 만가닥 | `1706` | 버섯류 |
| `grapefruit` | 🍏 자몽 | `0619` | 과일류 |
| `blueberry` | 🫐 블루베리 | `0659` | 과일류 |
| `dried_persimmon` | 🍏 곶감 | `0607` | 과일류 |
| `avocado` | 🥑 아보카도 | `0634` | 과일류 |
| `burdock` | 🥕 우엉 | `1104` | 근채류 |
| `jujube` | 🌰 대추 | `0702` | 견과류 |
| `apricot` | 🍏 살구 | `0610` | 과일류 |
| `yam` | 🌿 마 | `1408` | 산채류 |
| `bracken` | 🌿 고사리 | `1402` | 산채류 |
| `butterbur_stem` | 🥬 머위대 | `1024` | 엽경채류 |
| `stonecrop` | 🥬 돌나물 | `1027` | 엽경채류 |
| `bellflower_root` | 🌿 도라지 | `1407` | 산채류 |
| `soybean` | 🫘 콩 | `0301` | 두류 |
| `pomegranate` | 🍏 석류 | `0624` | 과일류 |
| `kidney_bean` | 🫘 강낭콩 | `0305` | 두류 |
| `pea` | 🫛 완두 | `0304` | 두류 |
| `radish_sprout` | 🥬 무순 | `1039` | 엽경채류 |
| `amaranth` | 🥬 비름 | `1021` | 엽경채류 |
| `coriander` | 🥬 고수 | `1052` | 엽경채류 |
| `bangpung` | 🌿 방풍나물 | `1420` | 산채류 |
| `cauliflower` | 🥦 콜리플라워 | `1312` | 양채류 |
| `vitamin_greens` | 🥦 비타민 | `1325` | 양채류 |
| `dallae` | 🥬 달래 | `1020` | 엽경채류 |
| `dragon_fruit` | 🍏 용과 | `0658` | 과일류 |
| `chestnut` | 🌰 밤 | `0701` | 견과류 |
| `shepherds_purse` | 🥬 냉이 | `1018` | 엽경채류 |
| `mustard_greens` | 🥬 겨자채 | `1050` | 엽경채류 |
| `dureup` | 🌿 두릅 | `1403` | 산채류 |

</details>

### 도매시장 코드 (`market`)

**가격은 공영 도매시장 32곳별로 예측합니다.** 시장 목록은 **`GET /markets`** (새로 만듦). 예전 `GET /regions`(전국 1개)는 그대로 두되 쓰지 않습니다.
- 시장 코드 = 팀 데이터 정산 자료의 도매시장코드 (`110001` 서울가락 등). 시세 화면 `GET /api/markets` 와 같은 코드
- `national` = 전국 도매시장 평균 (`market` 생략 시)
- **정의 위치: `shared/markets.json` 한 파일** (ml-api `app/core/markets.py` 와 화면 `frontend/src/mocks/market.js` 가 같이 읽음). 시장을 지역 단위로 묶는 방식이 정해지면 이 파일과 `markets.py` 만 고친다
- 없는 시장 코드 → `404`

| 시·도 | 도매시장 (코드) |
|---|---|
| 서울 | 서울가락 `110001` · 서울강서 `110008` |
| 부산 | 부산엄궁 `210001` · 부산반여 `210009` |
| 대구 | 대구북부 `220001` |
| 인천 | 인천남촌 `230001` · 인천삼산 `230003` |
| 광주 | 광주각화 `240001` · 광주서부 `240004` |
| 대전 | 대전오정 `250001` · 대전노은 `250003` |
| 울산 | 울산 `380201` |
| 경기 | 수원 `310101` · 안양 `310401` · 안산 `310901` · 구리 `311201` |
| 강원 | 춘천 `320101` · 원주 `320201` · 강릉 `320301` |
| 충북 | 청주 `330101` · 충주 `330201` |
| 충남 | 천안 `340101` |
| 전북 | 전주 `350101` · 익산 `350301` · 정읍 `350402` |
| 전남 | 순천 `360301` |
| 경북 | 포항 `370101` · 안동 `370401` · 구미 `371501` |
| 경남 | 창원팔용 `380101` · 창원내서 `380303` · 진주 `380401` |
| 세종 · 제주 | 공영 도매시장 없음 |

### 지역 코드 (`region`, 예전 방식)

`national`(전국)만 있습니다. 가격은 위 `market` 으로 고릅니다. (`ENABLE_REGIONAL_FORECAST` 는 남아 있지만 쓰지 않음)

### 예측 기간 (`horizon`)

- **오늘(기준일)로부터 며칠 뒤까지 예측할지, `1` ~ `365` 중 아무 정수** (11/4: 최대 30일 → 1년). 화면에서 사용자가 날짜를 고르면 `고른 날짜 - 오늘` 일수를 보냅니다.
- `GET /horizons` 의 `7`(1주) · `14`(2주) · `30`(1개월) · `90`(3개월) · `180`(6개월) · `365`(1년)은 **빠른 선택 버튼**용입니다.
- 0 이하나 366 이상을 보내면 `422` 입니다.
- 응답 `forecast` 에는 **오늘 다음 날부터 고른 날까지 일별 예측 경로**가 옵니다.
- **오차 범위(`lower`·`upper`) = 예측 ± 모델 검증 오차(WAPE)**, 품목·예측 기간별. 1주·2주·1개월·3개월·6개월 사이 날은 이어서 잡고, 1주보다 가까우면 √(일수/7) 만큼 줄여요
- **6개월(180일)보다 먼 날은 모델 검증이 없어서** 6개월 오차보다 넓게(1년에 1.5배) 잡고 `reference: "far"` — 화면에 "참고용"
- **기준선("오늘 가격 그대로")보다 0.1%p 넘게 나쁜 품목·기간은 `reference: "baseline"`** — 화면에 "참고용": 양배추 1개월·3·6개월, 당근 3·6개월, 무 1개월, 석류 6개월 (기간 구분: ~10일 1주, ~21일 2주, ~60일 1개월, ~135일 3개월, ~180일 6개월)
- ⚠️ **모델 담당 확인 필요:** 1~365일 **매일**의 예측값이 필요합니다 (월 단위 장기 모델이면 일별 경로를 어떻게 채울지 정해야 함).

### 에러 응답

| 상태 코드 | 의미 | 예시 |
|---|---|---|
| `404` | 없는 품목·시장·지역 코드 | `{"detail": "unknown item: durian"}` |
| `422` | 요청 형식이 틀림 (빠진 값, 허용 안 되는 값) | 아래 참고 |

```json
// 422 예시: horizon 에 366 을 보낸 경우
{
  "detail": [
    { "type": "less_than_equal", "loc": ["body", "horizon"],
      "msg": "Input should be less than or equal to 365", "input": 366 }
  ]
}
```

---

## 1. ML API (FastAPI)

> ⚠️ **현재는 더미(가짜) 예측값**을 돌려줍니다. 응답 **형식은 최종과 동일**하므로 이 형식대로 화면·연동을 개발하면 됩니다.
> 같은 품목·시장·날짜로 요청하면 항상 같은 값이 나옵니다.

### 한눈에 보기

| 메서드 | 주소 | 설명 | 사용 화면 |
|---|---|---|---|
| GET | `/health` | 서버 상태 확인 | - |
| GET | `/items` | 예측 품목 목록 (**50개**, `code4`·공영 부류, 11-11) | AI 가격예측·시세 › 품목 선택 상자 |
| GET | `/markets` | 공영 도매시장 32곳 (새로 만듦) | AI 가격예측 › 도매시장 선택 |
| GET | `/regions` | (예전 방식) 지역 목록 — 전국만, 화면에서 안 씀 | - |
| GET | `/horizons` | 빠른 선택 기간 (1주 ~ 1년) | AI 가격예측 › 날짜 선택 옆 버튼, 홈 기간 버튼 |
| POST | `/predict` | 품목·도매시장별 가격 예측 (최대 365일, 일별 경로). 기준일·앞쪽 실제 시세 일수·작년 같은 시기 선택 (11-11) | AI 가격예측 (`/ai`) |
| GET | `/predict/top-movers` | 급등락 예상 품목 | 홈 › AI 추천 · 급등락 예상 품목 |
| GET | `/recommend/crops` | 작물 추천에 쓰는 작물 목록 | 작물 추천 › 작물 정보 › 작물 고르기 |
| POST | `/recommend/crops` | 토지 위치(시·도)·토지별 평수·임대료·기존 작물·시작 날짜 → 심을 수 있는 작물(순이익 순, pH 를 낮춰야 하는 작물은 맨 아래) + 빠진 작물과 이유(`excluded`) | 작물 추천 (`/recommend`) › 내 땅으로 작물 고르기, 작물 정보 |
| GET | `/recommend/crops/{code}` | 작물 정보: 작형별 심는 기간·일수·10a당 수량·경영비·알맞은 pH (새로 만듦) | 작물 추천 › 작물 정보 (`/recommend?tab=info`) |
| POST | `/recommend/planting-dates` | 작물 → 앞으로 1년 심는 날별 마진 — **화면에서는 안 씀**(남겨 둠) | - |
| GET | `/recommend/crops/{code}/prices` | 작물의 **12개월** 예상 도매가(주 단위 53점, 11-11) | 작물 추천 › 작물 정보 |

---

### 1-1. `GET /health` 서버 상태

**응답 200**
```json
{ "status": "ok", "model_version": "dummy-0.1" }
```

---

### 1-2. `GET /items` 품목 목록

**응답 200** — **50개** (11-11), 물량 순위 순 (`shared/items50.json`). 품종(`varieties`)은 아직 넣지 않음 (1-2-1)
```json
[
  { "code": "onion", "name": "양파", "code4": "1201", "unit": "kg", "category": "조미채소류", "emoji": "🧅" },
  { "code": "radish", "name": "무", "code4": "1101", "unit": "kg", "category": "근채류", "emoji": "🌱" }
]
```

### 1-2-1. 품목 50개 · 세부 품종 (제안, 2026-11-06)

팀 회의로 품목을 **50개**로 줄이고, 품목마다 **세부 품종(예측 단위)** 으로 나눠 예측한다. 목록은 `shared/items50.json` 한 파일 (팀 자료 `50품목_예측단위_v3`, 예측 단위 326개).
지금 화면(가짜 데이터)은 이 파일로 동작하고, ml-api `/items`·`/predict` 도 11-11부터 이 50품목이다 (품종 `varieties`·`variety` 는 아직). 아래 모양으로 바꾸면 화면은 `api/*.js` 안쪽만 고치면 된다.

- `GET /items` → 50개 + `varieties`: `[{ "id": "apple-2", "label": "홍로", "kind": "named", "share": 14.6 }]`
  - `kind`: `named` 이름 있는 품종 · `type` 유형 묶음 · `other` 품종 이름 없는 물량을 철·산지로 나눈 것 (`label` 예: "기타 (봄 · 전남)")
  - `share`: 품목 안 물량 비중(%)
- `POST /predict` 요청에 `variety`(품종 id, 생략하면 품목 전체) 추가. 응답 `item_name` 은 "사과 홍로" 처럼
- `POST /recommend/crops` 결과에 `variety`(대표 품종 이름)와 `varieties`(같은 작물의 다른 품종 결과 목록) 추가 — 화면은 작물마다 순이익이 가장 높은 품종 하나를 보여 주고, 누르면 나머지를 펼친다
- 시세 API(2-15)의 `{item}` 자리에 품종도 받기: `?variety=apple-2` (가격·반입량을 그 품종만)
- 대시보드(오늘 시세·지수·순위)는 품종 없이 50품목 단위

### 1-3. `GET /markets` 도매시장 목록 (새로 만듦)

`/regions` 를 바꾸지 않고 **`/markets` 를 새로 만들었습니다** (지역과 시장은 다른 개념이라 따로 둠, 예전 `/regions` 를 쓰는 곳이 깨지지 않게).

**응답 200** — 32곳
```json
[
  { "code": "110001", "name": "서울가락", "sido": "서울", "sigungu": "송파구", "lat": 37.493, "lon": 127.112 },
  { "code": "110008", "name": "서울강서", "sido": "서울", "sigungu": "강서구", "lat": 37.564, "lon": 126.83 }
]
```

`GET /regions` (예전 방식) 은 `[{ "code": "national", "name": "전국" }]` 그대로입니다.

### 1-3-1. `GET /horizons` 예측 기간 목록

**응답 200**
```json
[
  { "days": 7,  "label": "1주" },
  { "days": 14, "label": "2주" },
  { "days": 30, "label": "1개월" },
  { "days": 90, "label": "3개월" },
  { "days": 180, "label": "6개월" },
  { "days": 365, "label": "1년" }
]
```

---

### 1-4. `POST /predict` 가격 예측

AI 가격예측 화면에서 도매시장·품목·**기준 날짜**를 고르면 호출합니다 (11-11 화면: 기준일부터 4주 = `horizon: 28`, 앞쪽 8주 = `history_days: 56`, 작년 같은 시기 = `last_year: true`).

**요청 본문**

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `item` | string | O | 품목 코드 |
| `market` | string | X | 도매시장 코드 (`GET /markets`). **생략하면 `national`(전국 평균)** |
| `horizon` | number | O | 예측 기간(일). **1 ~ 365 중 아무 값** (화면에서 고른 날짜 - 오늘) |
| `region` | string | X | (예전 방식) `national` 만. 쓰지 않아도 됨 |
| `base_date` | string | X | **기준일** (11-11). 생략하면 오늘. **오늘부터 1년 전까지** (밖이면 `422`). 이날 시세가 `base_price`, 다음 날부터 `horizon` 일을 예측 |
| `history_days` | number | X | 기준일 앞 실제 시세를 며칠 치 줄지 (11-11). 1 ~ 400, **기본 14** |
| `last_year` | boolean | X | `true` 면 작년 같은 시기 실제 시세(`last_year`)도 줌 (11-11). 기본 `false` |

```json
{ "item": "tomato", "market": "110001", "horizon": 90 }
// 11-11 화면 (기준일부터 4주, 앞쪽 8주, 작년 같은 시기)
{ "item": "napa_cabbage", "market": "110001", "horizon": 28, "base_date": "2026-11-10", "history_days": 56, "last_year": true }
```

**응답 200**

| 필드 | 타입 | 설명 | 화면 위치 |
|---|---|---|---|
| `item` / `item_name` / `code4` / `unit` | string | 품목 코드 / 이름 / 공영 품목코드 / 단위(항상 `kg`) | |
| `market` / `market_name` | string | 도매시장 코드·이름 (`national` = 전국 평균) | "서울가락 도매시장 기준" |
| `region` | string | (예전 방식) 항상 `national` | |
| `horizon` | number | 요청한 예측 기간 | |
| `base_date` | string | 기준일 (요청 `base_date`, 없으면 오늘) | 그래프 실제↔예측 경계 "기준일" |
| `base_price` | number | 기준일 공영도매시장 경매 단가 (원/kg) | |
| `history` | 배열 | 기준일 앞 실제 시세 `{date, price}` (`history_days` 일 + 기준일, 기본 15개) | 그래프 진한 초록 선 "올해 실제" (화면은 주 단위로 묶어 8점) |
| `forecast` | 배열 | 일별 예측 `{date, price, lower, upper}` — 기준일 다음 날부터 `horizon`일. `lower`·`upper` = 예측 ± 그날까지의 모델 검증 오차 | 초록 점선 "예측" + 초록 영역 "오차범위", 화면이 이 안에서 가장 비싼 날·싼 날을 찾음 |
| `predicted_price` | number | `horizon`일 후 예상 도매가 (= forecast 마지막 값) | "14일 후 예상 도매가" 금액 |
| `change_pct` | number | 기준가 대비 변동률 (%) | "▲ OO% vs 오늘" |
| `error_pct` | number | 고른 날의 예측 오차 ±% (모델 검증 WAPE, 품목·기간별) | "예측 오차 ±OO%" |
| `reference` | string \| null | 참고용: `far`(6개월보다 먼 날) · `baseline`(이 품목·기간은 기준선보다 나쁨) · `null` | "참고용" 표시 |
| `confidence` | number | 신뢰도 지수 = 100 − `error_pct` | "신뢰도 지수 OO/100" |
| `alerts` | 배열 | 예측이 부정확해질 수 있는 이상기후 구간 (없으면 `[]`) | 주황 구간 + "예측이 깨지는 구간 분석" |
| `last_year` | 배열 | 작년 같은 시기 실제 시세 `{date, price}` (요청 `last_year: true` 일 때만, 아니면 `[]`). **52주(364일) 전 같은 요일**, `history` 첫날 ~ `forecast` 마지막 날과 같은 기간. `date` 는 작년 날짜 (화면은 +364일 해서 겹쳐 그림) | 파란 선 "작년 같은 시기", "작년 최고 OO원" |
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
  "code4": "1001",
  "unit": "kg",
  "market": "national",
  "market_name": "전국 평균",
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
  "error_pct": 15.7,
  "reference": null,
  "confidence": 84,
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

**화면이 응답으로 계산하는 것** (서버가 따로 주지 않음): 오늘 ~ 고른 날짜 사이 `forecast` 에서 **가장 비싼 날·가장 싼 날** (같은 값이면 가까운 날), 오늘 대비 % = `(price - base_price) / base_price`

**에러**: 없는 `item`(50품목 밖 포함)·`market`·`region` → `404`, `horizon`이 1~365 밖 · `base_date` 가 오늘 뒤이거나 1년보다 전 · `history_days` 가 1~400 밖 → `422`

> 지금 ml-api 는 더미 예측기라 `history`·`last_year` 도 가짜 값이다. 실제 모델이 붙으면 둘 다 DB 의 실제 경매 단가(같은 품목·시장, 등급 구분 없음)로 채운다.

---

### 1-5. `GET /predict/top-movers` 급등락 예상 품목

홈 화면 "AI 추천 · 급등락 예상 품목" 카드에 씁니다. 변동률이 **크게 움직이는 순서**(상승·하락 모두, 절댓값 기준)로 정렬됩니다.

**쿼리 파라미터** (모두 생략 가능)

| 이름 | 기본값 | 설명 |
|---|---|---|
| `horizon` | `7` | 예측 기간 1~365일 |
| `limit` | `4` | 몇 개 받을지 (1~품목 수) |
| `market` | `national` | 도매시장 코드 (생략하면 전국 평균) |

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
| `confidence` | "AI 신뢰도 88%" (= 100 − 예측 오차) |
| `error_pct` · `reference` | 예측 오차 ±% · 참고용 (위 `/predict` 와 같음) |

---

### 1-6. 작물 추천 `/recommend`

> ⚠️ 값의 출처 (`ml-api/app/core/crop_calendar.py`, 프론트 예비 데이터 `frontend/src/mocks/recommend.js` 와 같음)
> - 10a당 수량·경영비·가격 수준: **농촌진흥청 2024년도 농산물소득조사**. 조사표 행과 맞는 작형은 `source: "rda"`, 나머지 작형과 조사표에 없는 작물(양파·봄동·마늘·쌀·콩)은 `source: "est"`(추정)
> - 심는 시기·수확 기간: 농사로 재배력 작형 기준. 보관 일수·상품화율·계절 가격 모양·출하 비중: 추정
> - 알맞은 흙 pH: 팀 자료 「작물별 땅 조건」 v4 엑셀 → **`shared/soil_ph.json`** (화면·ml-api `app/core/soil_ph.py` 가 같이 읽음). 값이 없는 작물은 추정해서 채우지 않음
> - 시장별 가격: 전국 평균 예측 × 시장 계수(0.9~1.1, 시세 가짜 데이터와 같은 규칙). 시장별 모델이 붙으면 `app/core/markets.py` 의 `market_factor` 자리를 바꾼다

**계산 기준**
- **순이익(마진)** = 예상 매출 − 총경영비
- 예상 매출 = Σ(월별 판매량 × 판 도매시장의 월별 예상가). 수확 기간(첫 수확 `harvest_start` ~ 마지막 수확 `harvest_end`)을 주 단위로 나눠, 여러 번 따는 작형(`multi_harvest`, 토마토·오이 등)은 처음·끝에 적고 가운데 많이 출하
- 판매량 = 10a당 수량 × 면적(평 ÷ 302.5) × 상품화율 (조사표 작물은 조사표 가격에 비품이 섞여 있어 상품화율 1)
- 총경영비 = 10a당 경영비(전국 평균, 고용 인건비 포함·자가노동비 제외) × 면적 + 사용자가 넣은 임대료(토지·농기계·시설, **만원 단위**, 그대로 더함)
- `margin_low`·`margin_high` = 가격이 예측 오차(`error_pct`)만큼 내리거나 올랐을 때. `error_pct` = 그 작물·수확 시작까지 남은 날의 모델 검증 오차(WAPE), `reference` = 참고용(위 `/predict` 와 같은 규칙)
- 땅 종류: `open` 노지 · `house` 시설 · `paddy` 논 · `orchard` 과수원 (과수는 다년생이라 날짜별 비교 안 함)
- **팔 시장 (11/4 팀 결정):** 수확한 지역 안의 도매시장에서 판다고 가정하고, **운송비와 유통 마진은 계산하지 않는다.**
  - `region`(시·도) 안의 공영 도매시장끼리 비교해서 작물마다 **순이익이 가장 높은 시장**을 결과로 준다 (예: 경기 → 수원·안양·안산·구리). 시장이 1곳이면 그 시장(예: 충남 → 천안)
  - 시·도 안에 공영 도매시장이 없으면(세종·제주) **다른 지역 시장을 섞지 않고 전국 도매시장 평균**으로 계산하고 `no_market: true`
  - "가까운 시장" 거리 계산은 없앴다 (토지 위치를 좌표가 아니라 시·도로만 받아서 정확히 계산할 수 없음)
- **기존 작물과 흙 pH:** 토지마다 기존에 키우던 작물(`lands[].prev_crop`, 선택)을 받으면
  - 흙 pH 어림 = 기존 작물 알맞은 pH 범위의 **가운데** (그 작물에 맞춰 관리해 왔다고 봄)
  - 흙 pH 가 후보 작물 알맞은 pH 최고값보다 **0.5 이상 높으면** pH 를 내리는 데 몇 달이 걸려서 **순이익과 상관없이 맨 아래로** (`demoted: true`, `ph.kind: "lower"`)
  - 0.5 보다 덜 높으면 `near`, 최저값보다 낮으면 `raise`(석회로 몇 주면 올림) — 순위는 그대로, 화면에 안내만
  - 기존 작물을 안 주면 pH 비교를 하지 않는다 (따로 키우던 작물 없음)

**`POST /recommend/crops`** 내 땅으로 작물 고르기
```json
// 요청 — start_date(심을 날짜) 는 오늘 ~ 1년 뒤 (밖이면 422, 11-11: 예전 30일). 임대료는 이번 작기 만원, 생략하면 0. prev_crop 은 shared/soil_ph.json 의 작물 이름, 생략 가능
{ "region": "경기",
  "lands": [{ "type": "open", "area_pyeong": 1200, "land_rent": 120 },
            { "type": "house", "area_pyeong": 600, "machine_rent": 35, "prev_crop": "상추" }],
  "start_date": "2026-11-11" }
// market 은 그 시·도 안 특정 시장으로 고정할 때만 (생략하면 순이익이 가장 높은 시장)
```
```json
// 응답 (일부) — results 는 순이익 높은 순, pH 를 낮춰야 하는 작물(demoted)은 맨 아래. 금액은 원
{ "start_date": "2026-11-11", "region": "경기", "no_market": false,
  "markets": [{ "code": "310101", "name": "수원" }, { "code": "310401", "name": "안양" }, { "code": "310901", "name": "안산" }, { "code": "311201", "name": "구리" }],
  "results": [{ "crop": "cucumber", "crop_name": "오이", "land_type": "house", "cropping": "촉성재배",
                "plant_date": "2026-11-11", "harvest_start": "2026-12-21", "harvest_end": "2027-04-10",
                "region": "경기", "market": { "code": "311201", "name": "구리" }, "no_market": false,
                "prev_crop": "상추", "soil_ph": 6.9, "ph": { "kind": "near", "min": 5.5, "max": 6.8, "gap": 0.1 }, "demoted": false,
                "price_per_kg": 2589, "revenue": 53915947, "cost": 24746694, "margin": 29169253, "margin_rate": 54.1,
                "market_compare": [
                  { "code": "310101", "name": "수원", "price_per_kg": 2445, "margin": 26166750, "margin_rate": 51.4, "factor": 1.0305, "best": false },
                  "… 안양 · 안산 …",
                  { "code": "311201", "name": "구리", "price_per_kg": 2589, "margin": 29169253, "margin_rate": 54.1, "factor": 1.0913, "best": true }],
                "…": "판매량·월별 출하·시나리오·조사표 비교 등 (아래 표)" }],
  "excluded": [{ "crop": "lettuce", "crop_name": "상추", "land_type": "house", "kind": "low",
                 "reason": "심을 수는 있지만 예상 마진률이 44%로, 추천 상위(3위 안)에 들지 못했어요. (5개 중 4위)" },
               { "crop": "paprika", "crop_name": "파프리카", "land_type": "house", "kind": "season",
                 "reason": "지금(11월)은 심는 시기가 아니에요. 시설 장기재배 8월 상순~8월 하순이에요. 다음 심는 때: 8/1부터(장기재배)" }],
  "unavailable": [ "… 심는 시기가 아닌 작물과 다음 심는 날 (예전 형식 그대로) …" ],
  "model_version": "dummy-0.1+crop-calendar-sample" }
```

`results[]` 의 그 밖의 항목: `days_to_harvest` · `harvest_days`(첫 수확 ~ 마지막 수확) · `multi_harvest` · `storage_days` · `storage_end` · `factor` · `national_price_per_kg` · `error_pct` · `yield_t` · `sellable_t` · `marketable_rate` · `base_cost` · `land_rent` · `machine_rent` · `margin_per_pyeong` · `margin_low` · `margin_high` · `national_margin` · `source` · `rda`(조사표 10a당 값) · `per_10a` · `shipments`(달마다 판매량·예상가·매출)

**빠진 이유(`excluded`)는 서버에서 계산합니다.** 작물 정보 탭이 ① 탭 입력으로 이 API 를 부르고, 고른 작물이 `excluded` 에 있으면 `reason` 을 그대로 보여 줍니다 (상위 3위 안이면 "추천 N위에 있어요").

| `kind` | 뜻 | 예 |
|---|---|---|
| `perennial` | 다년생 | 다년생 작물이라 날짜별 추천을 하지 않아요. |
| `land` | 고른 토지에서 못 기름 | 논 토지에서만 재배할 수 있어요. 고른 토지: 노지·시설 |
| `season` | 지금 심는 시기 아님 | 지금(11월)은 심는 시기가 아니에요. 노지 봄재배 3월 상순~3월 하순 … |
| `ph` | 흙 pH 를 낮춰야 해서 맨 아래로 | 심을 수는 있지만 노지 토지 흙(기존 작물 상추 기준 pH 약 6.9)이 알맞은 pH 5~6보다 0.9 높아서 … |
| `low` | 심을 수 있지만 상위 3위 밖 | 심을 수는 있지만 예상 마진률이 44%로, 추천 상위(3위 안)에 들지 못했어요. |

**`GET /recommend/crops/{code}`** 작물 정보 (새로 만듦, 작물 정보 탭)
```json
{ "crop": { "code": "cucumber", "name": "오이", "emoji": "🥒", "land_type": "house", "land_type_name": "시설", "perennial": false },
  "note": null, "marketable_rate": 1.0,
  "rda": { "row": "시설오이", "revenue": 25184000, "cost": 12300000, "income": 12884000, "kg": 10505, "price": 2397 },
  "soil_ph": { "name": "오이", "min": 5.5, "max": 6.8, "memo": "pH 4.3 이하 말라 죽음" },
  "croppings": [{ "name": "촉성재배", "plant_from": [10, 11], "plant_to": [12, 10], "days_to_harvest": 40, "harvest_days": 110,
                  "storage_days": 7, "multi_harvest": true, "yield_t_per_10a": 10.5, "cost_per_10a": 12300000, "source": "rda" }, "…"],
  "model_version": "dummy-0.1+crop-calendar-sample" }
```
- 다년생(`apple` 등): `note` 에 안내 문구, `croppings` 는 빈 배열 · 없는 작물 → `404`

**`POST /recommend/planting-dates`** 작물로 가장 좋은 심는 날 고르기 — **화면에서는 쓰지 않음** (11/4: "작물로 심을 날짜 고르기" 탭을 "작물 정보" 탭으로 바꿈). API 는 지우지 않고 남겨 둠
```json
// 요청 — region·market·임대료는 위와 같음 (생략 가능)
{ "crop": "tomato", "area_pyeong": 600, "region": "충남", "land_rent": 0, "machine_rent": 0 }
// 응답 — points 는 오늘부터 53주, 심을 수 없는 주는 option: null. best·top 은 results 항목과 같은 모양
```

**`GET /recommend/crops/{code}/prices`** 작물 상세 그래프: 오늘부터 **53점(12개월, 11-11 — 예전 57주)**, 주 단위 전국 공영도매 예상 경매 단가 `{ date, price, lower, upper }` (원/kg, 범위 = 모델 검증 오차). 고른 시장 그래프는 × `factor`

---

## 2. Backend (Spring Boot) — 프론트 기준 제안

> **아직 Spring 담당자가 확정하지 않은 "제안"입니다.** 프론트(`frontend/`)는 지금 이 모양의 가짜 데이터(`frontend/src/mocks/`)로 동작합니다.
> Spring 이 이 모양대로 응답하면 프론트는 `frontend/src/api/*.js` 함수 안쪽만 바꾸면 됩니다. 주소·필드를 바꾸고 싶으면 이 문서를 고치고 단톡방에 알려주세요.
> 공통: 가격은 원/kg 정수, 날짜는 `YYYY-MM-DD`, 일시는 ISO 8601 (`2026-10-19T14:03:00+09:00`).

### 한눈에 보기

| 메서드 | 주소 (제안) | 설명 | 사용 화면 | 프론트 함수 |
|---|---|---|---|---|
| GET | `/api/prices/today` | 오늘 시세 (전국 · 상 등급) + 전국 소매가, 직전 거래일 대비 | 홈 시세 띠·카드, 검색 품목 요약, 마이페이지 관심 품목 | `getTodayPrices` |
| GET | `/api/prices/index?days=30` | 지수: 전체 + 7묶음, 평소 가격(최근 60거래일 평균) = 100 | 홈 지수 카드 | `getMarketIndex` |
| GET | `/api/markets` | 도매시장 목록 (전국 평균 + 32곳) | 시세 › 시장 선택 | `getMarkets` |
| GET | `/api/prices/{item}/grades?market=&date=` | 등급별(특·상·중·하·평균) 가격 + 전국 소매가, 최근 5거래일 | 시세 › 등급별 가격 | `getGradePrices` |
| GET | `/api/prices/{item}/history?market=&grade=&date=&days=8` | 한 등급의 날짜별 가격·최고·최저·반입량 + 전국 소매가 | 시세 › 가격 추이 | `getPriceHistory` |
| GET | `/api/prices/{item}/origins?market=&date=` | 출하지역(시·도)별 평균 가격·반입량 | 시세 › 출하지역별 가격 | `getOriginPrices` |
| GET | `/api/volumes/{item}?market=&date=` | 순(10일) 단위 출하지역별 반입량 + 이번 순 요약 | 시세 › 반입 동향 | `getVolumeTrend` |
| GET | `/api/prices/{item}/markets` | 시장별 오늘 가격 (상 등급) | 통합 검색 › 시장별 오늘 시세 | `getMarketCompare` |
| GET | `/api/weather/regions` | 시·도 17곳 오늘 날씨 + 특보 | 홈 날씨 지도 | `getRegionalWeather` |
| POST | `/api/uploads` (multipart, `files` 여러 개) | 사진 업로드 → 사진 주소 목록 | 경매 등록, 게시판 글쓰기 | `uploadImages` |
| GET | `/api/posts?category=&q=&page=` | 게시글 목록 (숨김 제외, 15개씩) | 게시판 | `getPosts` |
| GET | `/api/posts/{id}` | 게시글 보기 (조회수 +1) | 게시판 › 글 | `getPost` |
| POST · PUT · DELETE | `/api/posts` · `/api/posts/{id}` | 글쓰기·수정·삭제 (작성자 본인만). **로그인 필요, 작성자는 세션의 회원** — 요청에 작성자 번호를 넣지 않음. 글쓰기 응답 `201 {"id"}` (11-10) | 게시판 › 글쓰기 | `createPost` · `updatePost` · `deletePost` |
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
| GET | `/api/auth/check?email=` · `?nickname=` | 이메일·닉네임 중복 확인 `{ "taken": true }` | 회원가입 [중복 확인] | `checkDuplicate` |
| GET | `/api/search?q=` | 통합 검색: 품목(별칭 포함)·경매·게시글·공지·뉴스 한 번에 | 헤더 검색 › 검색 결과 (`/search`) | `searchAll` |
| GET | `/api/search/suggest?q=` | 자동완성 (종류마다 2~3개) | 헤더 검색창 | `suggest` |
| GET | `/api/news?category=&item=&items=&q=&page=&size=` | 농업 뉴스 (최신순, 저장된 기사만) | 홈 헤드라인, 농업 뉴스 (`/news`), 검색 › 뉴스 | `getNews` |
| GET | `/api/news/trend?days=7&limit=5` | 최근 N일 기사에 많이 나온 품목 | 홈·농업 뉴스 › 많이 나온 품목 | `getNewsTrend` |
| GET | `/api/notices` | 공지 목록 (`show_on_home` 이면 홈 배너) | 홈 배너, 개발자 › 공지 | `getNotices` |
| GET · PATCH | `/api/me` | 내 정보 조회·수정 (이름·연락처·지역·농장명·관심 품목·알림 설정) | 마이페이지 › 내 정보 | `updateProfile` |
| POST | `/api/me/password` `{ "current", "next" }` | 비밀번호 변경 | 마이페이지 › 내 정보 | `changePassword` |
| DELETE | `/api/me` `{ "password" }` | 회원 탈퇴: 회원 정보와 쓴 글을 DB 에서 삭제 후 로그아웃 `204`, 비밀번호 틀림 `403` (진행 중 경매·최고가 입찰 있으면 `409`, 경매 재개 때) | 마이페이지 › 내 정보 | `withdraw` |
| GET | `/api/me/auctions` | 내가 등록한 경매 | 마이페이지 › 내 경매 | `getMyAuctions` |
| POST | `/api/auctions` | 경매 등록 (판매자만, `승인대기`로 생성) | 마이페이지 › 새 경매 등록 | `createAuction` |
| POST | `/api/auctions/{id}/cancel` | 내 경매 취소 (입찰 0건일 때만) | 마이페이지 › 내 경매 | `cancelMyAuction` |
| GET | `/api/me/notifications` | 내 알림 목록 | 종 아이콘, 마이페이지 › 알림 | `getNotifications` |
| GET | `/api/me/notifications/unread-count` | 안 읽은 알림 수 (30초마다 호출) | 종 아이콘 배지 | `getUnreadCount` |
| POST | `/api/me/notifications/read` `{ "id" }` (생략 시 전부) | 읽음 처리 | 종 아이콘, 마이페이지 › 알림 | `markRead` |
| POST | `/api/admin/auctions/{id}/bids/cancel` `{ "bid_ids", "reason" }` | 비정상 입찰 취소 → 현재가 재계산, 입찰자·판매자 알림 | 개발자 › 신고·분쟁, 회원·경매 관리 | `cancelBids` |
| | `/api/admin/...` | 공지·회원·경매 관리 (관리자만) | 개발자 페이지 | `api/admin.js` |

### 2-1. `GET /api/prices/today` 예시

```json
{
  "base_date": "2026-10-19",
  "compared_date": "2026-10-16",
  "market": "national",
  "grade": "HIGH",
  "unit": "kg",
  "items": [
    { "item": "napa_cabbage", "name": "배추", "emoji": "🥬", "category": "엽채류",
      "price": 800, "prev_price": 814, "change": -14, "change_pct": -1.7,
      "retail_price": 1890, "margin_pct": 136 }
  ]
}
```
- `compared_date` 는 직전 조사일 (주말·공휴일 제외) → 화면에 "10/16(금) 대비" 로 표시
- `price` 는 전국 도매시장 · 상 등급, `retail_price` 는 전국 소매가 (0번 "가격 기준")
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
{ "email": "farmer@farmbid.kr", "password": "abcd1234", "nickname": "새싹농부",
  "phone": "010-3333-4444", "region": "충남", "farm_name": "논산 햇살농장" }
```
- **11-07 변경:** 약관 동의 단계 삭제(`marketing` 없음), 이름 대신 **`nickname`**(2~20자, 중복 불가). 화면은 지금 `name` 에도 같은 값을 넣어 보낸다 (Spring 이 nickname 을 받으면 빼도 됨)
- 가입 전에 `GET /api/auth/check?email=a@b.kr` 또는 `?nickname=새싹농부` → `{ "taken": false }`. 화면의 [중복 확인] 이 부름. 가입 요청에서도 서버가 다시 확인해 중복이면 409
- **회원 유형을 고르지 않음:** 모든 회원이 입찰도 판매(경매 등록)도 할 수 있음. 서버가 `type: "member"` 로 저장하고, 관리자(`admin`)는 DB에서 지정
- `farm_name`(농장·상호명)은 선택. 있으면 경매 판매자 이름으로 함께 표시
- 비밀번호: 영문+숫자 8자 이상, **서버에서 암호화 저장**

#### 2-3-1. 로그인·세션 (11-10 Spring 구현)
| 주소 | 성공 | 실패 |
|---|---|---|
| `POST /api/auth/signup` | `201` 회원 정보 + 바로 로그인 | `409` 이메일·닉네임 중복, `422` 입력 오류 |
| `POST /api/auth/login` `{ "email", "password" }` | `200` 회원 정보 | `401` "이메일 또는 비밀번호가 맞지 않습니다"(가입 여부를 알려 주지 않음) |
| `POST /api/auth/logout` | `204` | — |
| `GET /api/auth/check?email=` · `?nickname=` | `{ "taken": false }` | `422` 둘 다 없음 |
| `GET /api/me` | `200` 지금 로그인한 회원 | `401` 로그인 안 함·세션 끝남·탈퇴로 지워짐 |
| `DELETE /api/me` `{ "password" }` | `204` 회원·쓴 글 삭제 + 로그아웃 (화면은 로그인 화면으로) | `403` 비밀번호 틀림 |

- **로그인 방식: 서버 세션.** 응답에 `JSESSIONID` 쿠키(HttpOnly, SameSite=Lax, 12시간)가 오고, 브라우저가 같은 주소의 다음 요청에 자동으로 붙인다. 화면은 토큰을 따로 저장하지 않는다.
- **회원 정보 응답:** `{ "id", "email", "name", "nickname", "phone", "region", "farmName", "type": "MEMBER", "status": "ACTIVE" }`. 비밀번호(해시)는 절대 없음.
- **오류 응답:** 회원 API 는 `{ "message": "화면에 보여줄 문장" }` (422 는 `detail` 에 칸별 오류도). 서버 내부 오류는 문장을 숨김.
- **비밀번호:** BCrypt 저장. 규칙은 영문+숫자 8~64자(키보드 문자만, 한글·띄어쓰기 안 됨).
- **로그인이 필요한 API 만들 때 (Spring):** `SecurityConfig` 의 `authorizeHttpRequests` 에 주소를 추가하고, 컨트롤러에서 `@AuthenticationPrincipal LoginUser me` 로 회원 번호(`me.id()`)를 꺼낸다. **요청 본문의 작성자 번호(authorId 등)를 믿지 말 것.**

### 2-4. 알림 항목 예시 (`GET /api/me/notifications`)

```json
{ "id": 12, "type": "auction", "title": "입찰 상회", "body": "'해남 월동배추 10kg × 20망'에 더 높은 입찰(240,000원)이 들어왔어요.",
  "link": "/auctions/2", "read": false, "at": "2026-10-19T14:03:00+09:00" }
```
- `type`: `auction`(경매·입찰) / `comment`(내 글에 댓글·내 댓글에 답글) / `weather`(이상기후 주의) / `notice`(공지). 회원이 내 정보에서 종류별로 끌 수 있음 → Spring 이 알림을 만들 때 회원 설정을 확인
- 알림을 만드는 때: 새 입찰(판매자), 상회 입찰(직전 최고가 입찰자), 경매 승인·중단(판매자), 입찰 취소(입찰자·판매자), 공지 등록 시 "회원 전체에게 알림" 선택, 관심 품목 예측에 이상기후 구간(`alerts`)이 생길 때(배치)
- 화면은 30초마다 `unread-count` 를 물어보는 방식(폴링). 실시간 푸시는 필요해지면 추가

### 2-5. 신고 — 삭제 (11-11)

신고 기능은 Spring 에 없고 팀 결정으로 **만들지 않는다**. 게시글·댓글 신고 버튼, 마이페이지 신고 내역, `POST /api/reports`·`GET /api/me/reports`·`PATCH /api/admin/reports/{id}` 를 모두 뺐다. 관리자는 게시판 관리에서 직접 글 숨김·이용 제한을 한다.

### 2-6. 경매 등록 요청 예시 (`POST /api/auctions`)

```json
{ "item": "potato", "title": "강원 수미감자 10kg × 3박스", "origin": "강원 평창", "weight_kg": 30,
  "start_price": 45000, "days": 3, "description": "오늘 수확한 수미감자입니다." }
```
- `item`: 16개 예측 품목 코드, 예측 품목이 아니면 `null`. **품질 등급은 받지 않음** (품질 분류 기준 없음)
- `days`: 1 / 3 / 5 / 7. 사진 업로드는 Spring 연결 때 추가
- **11-10 변경:** 회원 탈퇴는 회원 정보와 그 회원이 쓴 글·댓글을 **DB 에서 삭제**함 (내 댓글 → 내 글 → 회원 순서. 내 글의 남 댓글, 내 댓글의 남 답글도 함께 지워짐. 댓글 표 `post_comment`) (되돌릴 수 없음, 같은 이메일로 다시 가입 가능). 회원 **정지 기능은 없음** (users.status 열은 쓰지 않음)

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

> **11-11 제안 (마이페이지 "내가 쓴 글·댓글" 탭):** `GET /api/posts?mine=true` (로그인한 회원 글만, 다른 조건과 같이 씀), `GET /api/me/comments?page=` (내 댓글 + 그 글 제목·번호). 지금 Spring 에 없어 화면은 가짜 데이터로 보여 준다


```json
{ "rows": [ { "id": 18, "category": "정보", "title": "배추 가격 다음 주에 오를 것 같네요", "images": [],
              "author": "seller1", "author_name": "박농부", "created_at": "2026-10-19T15:01:00+09:00", "views": 132 } ],
  "total": 18, "page": 1, "pages": 2 }
```
- 말머리(`category`): `자유` / `질문` / `정보` / `거래후기`. 글쓰기 요청: `{ "category", "title"(2~80자), "body", "images" }`
- 목록 맨 위 공지는 `GET /api/notices` 를 그대로 사용 (관리자 › 공지사항에서 작성)
- 조회수는 같은 사람이 새로고침할 때마다 오르지 않게 서버에서 막는 것을 권장
- 목록 항목에 `comment_count`(지운 댓글 제외) 포함 → 제목 옆 `[3]`
- **11-10 Spring 구현** (`PostController`): 목록 `GET /api/posts?category=&q=&page=` (보이는 글만, 최신순 15개, 검색어는 제목·내용·닉네임, 검색하면 `snippet`), 보기 `GET /api/posts/{id}?view=true` (조회수는 같은 세션에서 글마다 한 번), 쓰기 `POST` `201 {"id"}`, 고치기 `PUT` (본인, `updated_at`), 지우기 `DELETE` `204` (본인, 댓글도 같이)
  - `author` 는 회원 번호(숫자), `category` 는 화면 이름(자유·질문·정보·거래후기, DB 값 FREE 등으로 보내도 됨). 제목 2~80자, 내용 5자 이상
  - 아직 없음: 사진 첨부(`images` 를 보내면 422), 관리자 숨김·삭제, 게시판 이용 제한 확인

### 2-10. 댓글 예시 (`GET /api/posts/{id}/comments`)

```json
[ { "id": 1, "parent_id": null, "author": "buyer1", "author_name": "김구매", "body": "저도 그래프 봤어요.",
    "created_at": "2026-10-19T15:40:00+09:00", "deleted": false,
    "replies": [ { "id": 2, "parent_id": 1, "author": "seller1", "author_name": "박농부", "body": "저는 1주 정도 보려고요.", "deleted": false } ] } ]
```
- 답글은 **1단계까지**. 답글에 답하면 같은 원댓글 아래에 붙음 (알림은 실제로 답한 댓글의 작성자에게)
- 댓글 1~500자. 답글이 달린 댓글을 지우면 `deleted: true` 로 남기고 내용은 비움("삭제된 댓글입니다")
- 알림: 내 글에 댓글 → 글쓴이, 내 댓글에 답글 → 원댓글 작성자 (본인이 쓴 건 알림 없음)
- **11-10 Spring 구현** (`CommentController`): `author` 는 회원 번호(숫자), `author_name` 은 닉네임. 쓰기 `201` 새 댓글, 지우기 `204`
  - 쓰기·지우기는 로그인 필수, 작성자는 세션 회원 (요청에 작성자 없음). 남의 댓글 지우기 `403`, 없는 글·숨긴 글 `404`, 빈 내용·500자 초과·지운 댓글에 답글 `422`
  - 답글을 지워 "삭제된 댓글" 원댓글에 남은 답글이 없으면 원댓글 자리도 지움
  - 아직 없음: 알림, 관리자 삭제(사유), 게시판 이용 제한 확인

### 2-11. 게시판 이용 제한 (`POST /api/admin/users/{id}/board-ban`)

```json
{ "days": 7, "reason": "스팸 게시 반복" }   // days: 3 / 7 / 30 / null(영구)
```
- 제한 중에는 **글·댓글 작성만 막음** (로그인·입찰·판매는 가능). 계정 전체 정지 기능은 없음 (11-10)
- 글쓰기·댓글 API 는 제한 중이면 `403` + 남은 기간·사유. 걸 때·풀 때 회원에게 알림
- 회원 정보에 `board_ban: { until, reason, at }` 저장 (`until` 이 null 이면 영구)

### 2-12. 품목 대표 사진
- 시세 카드·품목 버튼에 쓰는 품목 사진은 **서버가 아니라 프론트 파일**로 둠: `frontend/src/assets/items/<품목코드>.png` (규칙은 같은 폴더의 README)
- 사진이 없는 품목은 이모지(`GET /items` 의 `emoji`)로 대신 보여줌

### 2-13. 통합 검색 (`GET /api/search?q=사과`)
```json
{
  "q": "사과",
  "item": { "code": "apple", "name": "사과", "emoji": "🍎", "category": "과일류" },
  "auctions": [ { "id": 12, "title": "예산 부사 사과 5kg × 10박스", "current_bid": 268000, "ends_at": "...", "status": "진행중" } ],
  "posts": { "rows": [ { "id": 5, "category": "정보", "title": "사과 저장고 온도 관리 팁", "snippet": "…0~1℃, 습도 90%…", "author_name": "박농부", "comment_count": 2 } ], "total": 1 },
  "notices": [],
  "news": { "rows": [ "2-14 기사 모양" ], "total": 5, "updated_at": "2026-10-20T15:00:00+09:00" },
  "total": 7
}
```
- `item`: 검색어가 품목 이름이나 **별칭**(부사·홍로 → 사과, 신고배 → 배, 귤 → 감귤 …)이면 채움. 화면은 이걸로 시세·예측 카드를 그림 (시세·예측 값은 기존 시세 API·ML API 로 따로 불러옴)
- 경매는 진행중·낙찰·유찰만 (승인대기·취소·중단 제외), 진행 중 먼저. 게시글은 숨김 제외, `snippet` 은 본문에서 검색어 앞뒤 일부
- 뉴스는 제목·요약에 검색어가 있거나, 검색어가 가리키는 품목 태그가 붙은 기사 (예: "부사" 검색 → 사과 태그 기사도)
- 결과가 0건이면 화면이 품목 이름과 한 글자 다른지 보고 "혹시 '사과'를 찾으셨나요?" 를 띄움 (서버 일 아님)
- 검색은 Postgres 부분 일치(`ILIKE`)로 시작, 느려지면 `pg_trgm` 인덱스 추천 (한글 형태소 검색까지는 불필요)
- 별칭 목록·품목 찾기 규칙: `frontend/src/utils/itemMatch.js` (뉴스 태그와 같은 규칙)

### 2-14. 농업 뉴스 (`GET /api/news`)
```json
{
  "rows": [
    {
      "id": 1,
      "title": "김장철 앞두고 배추 출하량 늘어… 도매가 2주 연속 하락세",
      "summary": "김장철을 앞두고 해남·영암 등 월동배추 주산지의 출하가…",
      "press": "○○일보",
      "url": "https://언론사 원문 주소",
      "published_at": "2026-10-20T14:28:00+09:00",
      "category": "가격·수급",
      "items": ["napa_cabbage"],
      "item_tags": [ { "item": "napa_cabbage", "name": "배추", "emoji": "🥬" } ],
      "press_count": 3, "presses": ["○○일보", "△△뉴스", "□□경제"]
    }
  ],
  "total": 64, "page": 1, "pages": 5,
  "updated_at": "2026-10-20T15:00:00+09:00",
  "next_update_at": "2026-10-20T16:00:00+09:00"
}
```
- 파라미터: `category`(가격·수급 / 기상·재해 / 정책·지원 / 유통·경매), `item`(품목 하나), `items`(쉼표로 여러 개 = 내 관심 품목만), `q`(제목·요약 검색), `page`·`size`(기본 15)
- **수집 (Spring 스케줄러, 1시간마다)**
  - 네이버 **뉴스 검색 API** `GET https://openapi.naver.com/v1/search/news.json?query=&display=100&sort=date` (무료, 하루 25,000회). 네이버 페이지 크롤링은 하지 않음 (약관·구조 변경 위험)
  - 검색어: 품목 이름 16개(+ "농산물 가격", "농산물 수급" 등) → 한 번에 50회 안팎 호출, 1시간마다여도 하루 1,200회
  - **마지막 성공 시각 이후** 기사만 받음 (최신순으로 받다가 그보다 오래된 기사가 나오면 멈춤). 서버가 꺼져 있었으면 켜질 때 한 번 바로 수집
  - API 키(Client ID·Secret)는 **서버 환경변수에만**. 화면이 네이버를 직접 부르지 않음 (키 노출 + CORS)
  - 시간대: 서버 `TZ=Asia/Seoul`, `pubDate`(예: `Mon, 20 Oct 2026 14:28:00 +0900`)를 시간대 포함해 저장
  - 네이버 응답의 `<b>` 태그·`&quot;` 같은 HTML 은 지우고 저장. `originallink`(없으면 `link`)를 **고유 키**로 같은 기사 한 번만 저장
  - 언론사 이름은 API 가 주지 않음 → 원문 주소 도메인으로 표를 만들어 붙임 (없으면 도메인 그대로)
  - 실패해도 기존 기사는 그대로 보여주고, 다음 수집 때 다시 시도. 화면은 `updated_at` 을 "15:00 업데이트" 로 표시
  - 보관 기간 90일 (지난 기사는 지움)
- **품목·분류 붙이기 (저장할 때 한 번)** — 규칙은 `frontend/src/utils/itemMatch.js`, `frontend/src/mocks/news.js` 와 같게
  - 농업 기사 거르기: "농산물·농가·산지·도매·출하·작황·재배·수확·시세·가격·kg …" 중 하나도 없으면 저장하지 않음 ("사과문", "당근마켓" 기사 제외)
  - 품목: 이름·별칭 글자 찾기, 긴 이름 먼저("양배추" 안의 "배추" 중복 방지). 한 글자 품목(배·무·귤)은 앞뒤가 다른 한글이면 제외("배송", "재배", "무료")
  - 분류: 분류별 단어 목록 점수 (제목 2점, 요약 1점), 가장 높은 분류. 없으면 `기타`
  - 형태소 분석은 쓰지 않음. 배·무 오류가 많으면 그때 Kiwi(`kiwipiepy`) 추가
- 기사 **본문은 저장·표시하지 않음** (저작권). 제목·요약 + 원문 링크만, 화면에 "뉴스 제공: 네이버 검색 API · 각 언론사" 표시
- **많이 다룬 뉴스 (11-11):** 같은 제목(띄어쓰기·기호를 뺀 제목)을 다른 언론사가 또 실으면 기사는 한 번만 저장하고 `presses`(언론사 이름 목록)·`press_count`(언론사 수)만 늘린다 (`collector/news/collect_news.py`). 화면 뉴스 › "많이 다룬 뉴스"는 오늘 기사를 `press_count` 많은 순으로 5개. 예전에 저장된 기사는 값이 없어 1로 본다. 조회수 기준 "많이 본 뉴스"는 클릭을 셀 곳이 없어 만들지 않음
- **내 관심 품목 뉴스 (11-11):** 로그인한 회원의 관심 품목으로 `items=` 를 걸어 부름 (기사에 이미 품목 태그가 있음). 로그인 안 했으면 로그인 안내
- `GET /api/news/trend` 응답: `[ { "item": "napa_cabbage", "name": "배추", "emoji": "🥬", "count": 48 } ]`

### 2-15. 시세·수급 (`/market`)

화면 순서: 조건(날짜 · 시장 · 품목) → 등급별 가격 한눈에 보기 → 가격 추이 · 출하지역별 가격 → 반입 동향. 유통마진·유통처별 비교·월별 생산량(수급 리포트)은 뺐다.

공통 파라미터
- `market`: `GET /api/markets` 의 `code` (생략 = `national` 전국 평균)
- `date`: 생략하면 최근 거래일. 거래가 없는 날(주말 등)을 주면 **그 전 가장 가까운 거래일** (`base_date` 로 돌려줌)
- `grade`: `SPECIAL` · `HIGH` · `MID` · `LOW` · `ALL` (생략 = `HIGH`)
- 그 날 그 등급 거래가 없으면 가격은 `null` → 화면은 비워 두고 "이 날은 하 등급 거래가 없어요"

`GET /api/markets`
```json
[{ "code": "national", "name": "전국 도매시장 평균" },
 { "code": "110001", "name": "서울가락", "sido": "서울", "sigungu": "송파구", "lat": 37.493, "lon": 127.112,
   "top_item": "onion", "items": ["potato", "onion", "..."] }]
```
- `code` 는 정산 자료의 도매시장코드 (팀 데이터 `매핑_시장.csv`), 위도·경도는 대략값 (`05_시장위치.csv`) → 홈 지도에 시장 위치 표시
- `top_item`: 최근 거래일 물량 1위 품목, `items`: 최근 1년 거래 기록이 있는 품목 (예: 안동은 버섯류·무·대파 없음)
- 홈 지도의 "시세 보기"는 관심 품목 중 그 시장에서 거래하는 첫 품목, 없으면 `top_item` 으로 시세 화면을 연다

`GET /api/prices/radish/grades?market=national&date=2026-10-20`
```json
{
  "item": "radish", "market": "national", "base_date": "2026-10-20", "compared_date": "2026-10-19", "unit": "kg",
  "grades": [
    { "grade": "HIGH", "price": 639, "prev_price": 692, "change": -53, "change_pct": -7.7, "year_ago_pct": 0.3,
      "points": [{ "date": "2026-10-14", "price": 750 }, { "date": "2026-10-20", "price": 639 }] },
    { "grade": "LOW", "price": null, "prev_price": 541, "change": null, "change_pct": null, "year_ago_pct": null,
      "points": [{ "date": "2026-10-20", "price": null }] }
  ],
  "retail": { "price": 1480, "prev_price": 1460, "change": 20, "change_pct": 1.4, "year_ago_pct": 12.0,
              "points": [{ "date": "2026-10-20", "price": 1480 }] }
}
```
- `grades` 는 `SPECIAL`·`HIGH`·`MID`·`LOW`·`ALL` 5개 모두, `points` 는 최근 5거래일 (예시는 줄임)
- `year_ago_pct`: 1년 전 같은 무렵 거래일 대비

`GET /api/prices/radish/history?market=national&grade=HIGH&days=8`
```json
{ "item": "radish", "market": "national", "grade": "HIGH", "unit": "kg",
  "points": [{ "date": "2026-10-20", "price": 639, "change": -53, "change_pct": -7.7, "high": 660, "low": 610, "volume_t": 429, "retail": 1480 }] }
```
- `volume_t`: 그 날 반입량(톤, 등급 합계). `retail` 은 등급과 상관없이 같은 값

`GET /api/prices/radish/origins?market=national&date=2026-10-20`
```json
{ "item": "radish", "market": "national", "base_date": "2026-10-20", "compared_date": "2026-10-19", "unit": "kg",
  "regions": [{ "region": "강원", "price": 588, "change": -42, "change_pct": -6.7, "high": 640, "low": 520, "volume_t": 296 }] }
```
- 출하지역은 **시·도** 단위 (DB `price_daily.origin_region_id`), 가격은 등급 평균(`ALL`), 반입량 많은 순

`GET /api/volumes/radish?market=national&date=2026-10-20`
```json
{ "item": "radish", "market": "national", "unit": "톤",
  "periods": [{ "period": "10월 중순", "start": "2026-10-11", "end": "2026-10-20",
                "top1": { "region": "강원", "volume_t": 4561 }, "top2": { "region": "경기", "volume_t": 733 },
                "others_t": 1514, "total_t": 6808 }],
  "summary": { "period": "10월 중순",
               "top": [{ "region": "강원", "volume_t": 4561, "share_pct": 67, "year_ago_pct": 17.0 }],
               "others_t": 1514, "total_t": 6808, "change_t": 758, "change_pct": 12.5 } }
```
- 순 = 1~10일 상순, 11~20일 중순, 21일~말일 하순. 최근 9순, 오래된 순 → 최근 순
- 이번 순은 `date` 까지의 누적이라, `change_t`·`change_pct` 는 **지난 순의 같은 거래일 수까지** 더한 값과 비교한다

### 2-16. 지수 (`GET /api/prices/index?days=30`)

홈 지수 카드 8개(전체 + 7묶음). 가격 = 전국 도매시장 · 상 등급. 묶음은 공영 부류를 합친 것으로 `shared/items.json` 의 `index_groups` 한 곳에 있다.

| 묶음 | 공영 부류 | 품목 수 |
|---|---|---|
| 잎채소 | 엽경채류 | 26 |
| 양채·나물 | 양채류 + 산채류 | 20 |
| 열매채소 | 과채류 | 9 |
| 양념채소 | 조미채소류 | 9 |
| 뿌리·곡물 | 근채류 + 서류 + 두류 + 잡곡 | 11 |
| 과일 | 과일류 + 견과류 | 26 |
| 버섯 | 버섯류 | 6 |

```json
{ "base_date": "2026-11-05", "base_days": 60,
  "groups": [{ "code": "all", "name": "전체", "emoji": "📊", "categories": null, "item_count": 107,
               "value": 99.7, "change": -0.2, "change_pct": -0.2,
               "points": [{ "date": "2026-09-24", "value": 98.1 }, { "date": "2026-11-05", "value": 99.7 }] },
             { "code": "leafy", "name": "잎채소", "emoji": "🥬", "categories": ["엽경채류"], "item_count": 26, "...": "..." }] }
```
- 계산: 품목마다 평소 가격(최근 `base_days` 거래일 평균)을 100 으로 바꾼 뒤, 첫날 값 = 그 날 거래된 품목의 평균. 그다음 날부터는 **전날·당일 둘 다 거래된 품목**의 "당일 ÷ 전날" 평균을 곱해 이어 붙인다 (철이 지나 거래가 끊기는 품목이 있어도 튀지 않게). 원 단위 평균이 아니라 비율 평균이라 비싼 품목이 지수를 끌고 가지 않는다
- `points` 는 최근 `days` 거래일, 오래된 날 → 최근. 수입 위주 품목도 포함 (지금은 107품목 전부)
- 카드 아래 "AI 30일 뒤 ▲ n% 상승" 은 이 API 가 아니라 화면에서 `GET /predict/top-movers?horizon=30&limit=107` 의 묶음 품목 `change_pct` 평균으로 계산

## 3. 정해야 할 것

- [ ] 프론트가 ML API를 **직접 호출**할지, **Spring을 거쳐** 호출할지
- [ ] 신뢰도 지수(`confidence`) 계산 방식 (예: 백테스트 오차율 기반)
- [ ] 예측을 **요청 때마다 계산**할지, **매일 미리 계산해 DB에 저장**할지
- [ ] 품목·지역 코드를 위 영어 코드로 확정할지 (KAMIS 품목코드와의 매핑 포함)
- [ ] 비정상 입찰 판단 기준 (지금은 관리자가 신고를 보고 직접 골라 취소. 입찰 IP 저장 여부)
- [ ] 새 DB 테이블: 관심 품목, 알림 (+ 입찰에 `cancelled`, 회원에 `status`·알림 설정). 신고는 만들지 않음 (11-11)
- [ ] 새 DB 테이블: 게시글(숨김 여부·사유 포함), 사진 주소(경매·게시글 공용), 경매에 사진 목록
- [ ] 예측 모델이 1~30일 **매일** 값을 낼 수 있는지 (사용자가 아무 날짜나 고름)
- [ ] 관리자 사이트 배포 주소 (같은 도메인 `/admin/` 또는 `admin.` 서브도메인)
- [ ] 새 DB 테이블: 댓글(답글은 `parent_id`, `deleted`), 회원에 게시판 이용 제한(`board_ban_until`·사유)
- [ ] 회원 유형 정리: `buyer`·`seller` 를 `member` 하나로 (이미 만든 테이블이 있으면 변경)
- [ ] 새 DB 테이블: 뉴스(`url` 고유, 제목·요약·언론사·발행 시각·분류·품목 목록), 수집 기록(마지막 성공 시각)
- [ ] 네이버 개발자센터 애플리케이션 등록·API 키 발급 담당 (키는 `.env`, 커밋 금지)
- [ ] 뉴스 수집을 Spring 스케줄러에서 할지, 별도 수집 스크립트(시세·날씨 수집과 같은 곳)에서 할지
- [ ] 도매시장 32곳: 팀 데이터 코드(110001 등)로 맞춤 → DB `market` 테이블도 같은 코드 쓰기 (`인천남촌`/`인천구월` 이름 통일)
- [ ] KAMIS·aT 원본 등급(특·상·중·하 / 상품·중품 등)을 `SPECIAL`·`HIGH`·`MID`·`LOW` 로 바꾸는 규칙, 평균(`ALL`) 계산 방법
- [ ] 한 품목의 여러 품종(예: 무 = 가을무·고랭지무)을 하나로 합치는 방법 (거래량 가중 평균 등)
- [ ] 월별 생산량(`supply_stat`)은 화면에서 뺐음 → 테이블을 남길지

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
| 2026-10-20 | 통합 검색(`/api/search`, 자동완성), 농업 뉴스(`/api/news`, 1시간마다 네이버 뉴스 검색 API 수집·품목·분류 규칙) 제안 추가 | |
| 2026-10-21 | 가격 기준 확정(전국 도매시장 · 상 등급, 예측도 같은 기준). 시세 API 제안 변경: 등급별·출하지역별·순별 반입량·시장 목록 추가, 수급 리포트(`/api/supply`) 삭제 | |
| 2026-10-21 | `GET /api/markets` 에 팀 데이터 시장코드·위치·물량 1위 품목·거래 품목 추가 (홈 지도 도매시장 표시) | |
| 2026-11-03 | 작물 추천 API(`/recommend/*`) 추가 (작물 달력 샘플 값). 경매는 팀 결정으로 보류: 화면에서 숨김(경매 API 제안은 그대로 둠) | |
| 2026-11-04 | 작물 추천: 농진청 2024 소득조사 값·실제 작형 수확 기간·보관 일수, 월별 출하량 × 월별 예상가, 임대료 입력, 토지 위치(`region`)·판 도매시장(`market`)·시장별 비교, 가격 하락·상승 시나리오, 출처 표시(`source`) | |
| 2026-11-04 | **11/4 팀 회의 반영.** 품목 16 → **107개**(`code4` 공영 품목코드·공영 부류, 기존 16개 코드 유지, 목록은 `shared/items.json`). 가격 예측을 **도매시장 32곳별**로: `GET /markets` 새로 만듦(`/regions` 는 예전 방식으로 남김, 시장 목록은 `shared/markets.json`), `POST /predict` 에 `market`, `horizon` 상한 30 → **365**, `/horizons` 에 3개월·6개월·1년. 작물 추천: "가까운 시장" 거리 계산 없애고 **시·도 안 도매시장끼리 비교**(없으면 전국 평균, 다른 지역 섞지 않음), 토지별 기존 작물(`prev_crop`) → 흙 pH 어림, 0.5 이상 낮춰야 하면 맨 아래로(`ph`·`demoted`, pH 표는 `shared/soil_ph.json`), 빠진 작물과 이유 `excluded`(서버 계산), `GET /recommend/crops/{code}` 작물 정보 새로 만듦, `planting-dates` 는 화면에서 안 씀. 운송비·유통 마진은 계산하지 않음(수확한 지역 안 시장에서 판다고 가정) | |
| 2026-11-05 | **107품목 모델 결과 반영.** 예측 오차·신뢰도를 모델 검증 결과(품목·기간별 WAPE, `shared/model_accuracy.json`)로: `/predict`·`/predict/top-movers` 에 `error_pct`·`reference` 추가, `confidence` = 100 − 오차, 띠 = 예측 ± 오차, 6개월보다 먼 날은 넓게·참고용(`far`), 기준선보다 나쁜 품목·기간 참고용(`baseline`: 양배추 1·3·6개월, 당근 3·6개월, 무 1개월, 석류 6개월). 작물 추천 `error_pct` 도 같은 값, `reference` 추가. 예측 가격 기준 = 공영도매시장 경매 단가(원/kg). 1-6 의 `/recommend/crops/{code}/prices` 설명을 되살림 | |
| 2026-11-05 | **홈 대시보드(주식 앱 형태)·예측 정확도 경고.** Spring 제안 추가: `GET /api/prices/index`(2-16, 전체 + 7묶음 지수, 묶음은 `shared/items.json` 의 `index_groups` 에 추가). 홈은 오늘 시세·AI 30일 예측(`/predict/top-movers?horizon=30&limit=107`)·가격 추이(`/api/prices/{item}/history`, 캔들 = 전 거래일 가격·당일 가격·최고·최저)를 같이 씀. 가격 예측 화면: 1개월 오차 35% 이상이거나 참고용 기간이 있는 품목(14개)을 "예측 정확도 낮음"으로 표시 — 기준·문구는 샘플(추후 확정). 프론트 가짜 데이터: `mocks/marketIndex.js` 추가, 이모지가 빈 문자열인 품목도 부류 기본 이모지로 (ml-api 와 같게) | |
| 2026-11-06 | **품목 50개 · 세부 품종(제안, 1-2-1).** `shared/items50.json` 추가(50품목 × 예측 단위 326개). 화면 가짜 데이터: 오늘 시세·급등락·지수를 50품목으로, 가격 예측·시세는 부류 → 품목 → 품종으로 고름, 작물 추천은 작물마다 대표 품종 + 다른 품종 펼치기. 품종 가격은 아직 가짜(품목 값 × 품종 계수). 가격 예측 최근 검색은 로그인한 사람만(지금은 브라우저 저장). 대시보드·가격 예측·작물 추천의 설명 글씨 정리 | |
| 2026-11-07 | 회원가입: 약관 동의(`marketing`) 삭제, `name` → `nickname`, 중복 확인 `GET /api/auth/check` 제안 추가(2-3). 가격 예측 도매시장 고르기는 `GET /api/markets`(전국 평균 + 32곳, 시장별 `items` = 최근 1년 거래 품목)를 씀 | |
| 2026-11-11 | **새 디자인(v17) 반영.** ML API: `GET /items`·`POST /predict`·`top-movers` 를 **예측 품목 50개**(`shared/items50.json`)로 — 50개 밖은 `404`(양송이 `button_mushroom` 빠짐). `POST /predict` 에 `base_date`(기준일, 오늘~1년 전)·`history_days`(1~400, 기본 14)·`last_year`(작년 같은 시기 실제 시세, 52주 전 같은 요일) 추가. 작물 추천 `start_date` 를 오늘~30일 → **오늘~1년**, `/recommend/crops/{code}/prices` 를 13개월 57점 → **12개월 53점**. 뉴스 수집: 같은 소식을 실은 언론사 수 `press_count`·`presses`(많이 다룬 뉴스). 신고 기능 삭제(2-5, 한눈에 보기·알림 종류에서 뺌). 마이페이지 내가 쓴 글·댓글 API 제안(2-9). 프론트 가짜 데이터(`frontend/src/mocks`)도 같이: 예측 `last_year`·`base_date`, 가격 경로 53점, 뉴스 `press_count`, 알림 종류에서 신고 뺌. 회원가입 요청에서 `marketing` 을 보내지 않음(마케팅 동의는 넣지 않기로 함 — Spring 의 `marketing` 칸은 비어 들어감) | |
