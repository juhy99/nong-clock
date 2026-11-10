# 시세 화면을 실제 데이터로 보기 (2026-11-09)

```
경매원장(월별 CSV) → 수집기 collector/daily (import → build_tables) → 데이터 폴더/tables/*.csv
  → load_db.py → PostgreSQL(docker db) → Spring /api/prices… → 화면 /market
```

## 내 PC 시험
`scripts\시세화면_시험실행.bat` 더블클릭 (Docker Desktop 켜 둔 상태). 데이터 폴더가 `D:\nong-clock-data\05_DB적재\data` 가 아니면 bat 맨 위 `DATA` 한 줄만 고침
1. `docker compose -f docker-compose.yml -f docker-compose.local.yml --profile spring up -d --build db backend`
2. 수집기 표를 DB 에 넣기 (`load_db.py --init`, 파이썬은 도커 이미지로 실행)
3. `frontend` 에서 `npm run dev` → http://localhost:5173/market (vite 가 /api 를 localhost:8080 Spring 으로 넘김)

## 코드와 데이터 나누기
- 코드(git): `collector/daily/` — 팀원 수집기(farmbid_daily) 그대로 + 데이터 폴더를 `FARMBID_DATA` 로 바꿀 수 있게 고침, 과거 시세를 달 묶음으로 만드는 `tools/build_prices_chunk.py`, 달마다 전 기간을 다시 읽던 `read_auction` 고침
- 데이터(git 밖): `FARMBID_DATA` 폴더의 raw(원장 일별) · tables(적재용 CSV) · hist · weather · log. `collector/daily/.env` 에 `FARMBID_DATA=...`
- 키·비밀번호: `collector/daily/.env`, 저장소 `.env`, `frontend/.env` (모두 git 에 안 올라감)

## Spring 시세 API (명세서 2-1 · 2-15 주소 그대로)
`backend-spring/.../` 역할별 폴더 — controller/PriceController(주소 7개) · service/PriceService(계산) · service/VarietyCatalog(품종 id → 예측 단위 이름, shared/items50.json) · repository/PriceSql · JdbcPriceSql(SQL 실행)
- 시세 표는 JPA 엔티티 없이 SQL(NamedParameterJdbcTemplate)로 읽는다 → `ddl-auto: validate` 와 무관
- 계산 규칙은 같은 규칙의 파이썬판과 77개 호출 결과를 비교해 같음을 확인 (0.1톤 반올림 2곳만 다름)

## 같이 고친 것
| 파일 | 내용 |
|---|---|
| `domain/User.java` · `service/UserService.java` | 표에 없는 `region` 열 → `region_id` (서버가 validate 에서 안 켜지던 문제). 지역 이름 → 번호는 UserService |
| `application.yml` | 비밀번호 `${DB_PASSWORD:1234}`, `shared.dir` |
| `docker-compose.yml` | backend 에 shared 폴더·SHARED_DIR, web 빌드에 `PRICE_SOURCE` (기본 mock) |
| `docker-compose.local.yml` | 내 PC 에서만 backend 8080 열기 |
| `frontend/src/api/market.js` · `client.js` · `vite.config.js` · `Dockerfile` | `VITE_PRICE_SOURCE=db` 이면 실제 시세, 아니면 가짜 (서버 배포본 기본은 가짜) |

## 서버에서 켜려면
서버 `.env` 에 `COMPOSE_PROFILES=spring`, `PRICE_SOURCE=db` + 서버 DB 에 수집기 표 적재

## 11-09 추가분(팀원 추가분_1109) 반영
- `D:\nong-clock-data\02_전처리` 에 풀어 넣음 (새 폴더 100~110번 12개, 갱신 파일은 덮어쓰기 전 `_백업_추가분1109_덮어쓰기전` 에 보관)
- **소매가:** KAMIS 일별 소매가격(~2026-11-09)을 `tools/import_kamis_csv.py` 로 수집기 형식으로 나눠 `retail_price_daily` 를 만듦 (2025-01~, 22품목: kg·g 단위 규격이 있는 품목만, 품목마다 규격 하나로 고정). Spring 시세 API 가 오늘 시세·등급 카드·가격 추이에 소매가를 함께 돌려줌
- **품종 단위 v3 326 → v3b 322:** 수집기 `ref/variety_unit*.csv` 와 `shared/items50.json` 에서 감귤 천혜향·레드향·황금향·카라향을 만감 단위로 합침. 품종코드 표는 v3b 정의(예측 모델과 같은 것)로 다시 만듦 — 마늘 1209/22·1209/01 이 두 단위에 겹쳐 들어가던 것도 바로잡음. 옛 표는 `collector/daily/ref_old/`
- 시세(도매)는 그대로 2026-11-03 까지: 추가분의 26번 12·13 표는 11-07 까지지만 30품목뿐이라 50품목 표를 이어 붙이지 않음 (원장 원본이나 API 키가 있어야 11-04 이후 50품목을 채울 수 있음)

## 시장별 등급 빈칸 고침 (11-09)
- **사실:** 최근 30일, 시장×품목 1,579개 조합에서 그 등급이 거래일의 절반 이상 나온 비율은 특 80% · 상 46% · 보통 22% · 하 20%. 전국 평균의 상은 100%. 시장마다 등급을 붙이는 방식이 달라서 생기는 빈칸이다 (예: 부산엄궁 양배추는 특·보통만 씀). 데이터를 더 구해도 채울 수 없다.
- **도매 시세는 국산만:** 수집기 `build_tables.py` 가 `price_daily`(등급별 시세)를 국산 거래만으로 만든다. 수입(물량의 약 1.9%, 대부분 중국)은 `price_origin_daily` 에 산지 "수입"으로 남는다. 예를 들어 부산엄궁 양배추 10-30은 수입이 섞이면 20.6t이었고, 국산만 보면 3.6t이다.
- **Spring:** `/api/prices/{item}/grades` 응답에 등급마다 `days_30`(최근 30일 거래일 수)이 들어가고, 맨 위에도 `days_30`(평균 기준 거래일 수)이 들어간다.
- **화면(Market.jsx):**
  - 전국 평균일 때 기본 등급은 상이다. 시장을 고르면 기본 등급은 평균으로 바뀌고, 시장을 바꿀 때마다 등급은 그 기본값으로 돌아간다.
  - 최근 30일 거래일이 평균의 절반 미만인 등급 카드와 추이 버튼은 숨기고, "이 시장은 최근 30일 ○ 등급 거래가 거의 없어 숨겼어요"라고 안내한다. 평균과 지금 고른 등급은 늘 보인다.
  - 품종을 고른 채 시장을 고르면 "품종별 시세는 전국 평균만 있어요"라고 안내한다.

## 데이터 점검과 원장 입력 오류 거르기 (11-09)
적재용 CSV 13개를 전부 점검했다 (DB 는 이 파일을 그대로 넣으므로 같은 점검).
- **구조 점검 — 모두 통과:**
  - 열쇠 중복 0, 빈칸 0, 0 이하 값 0, 없는 시장·품목·지역·단위 번호 0.
  - 최저가 ≤ 최고가.
  - 등급별 물량 합 ≤ 평균(ALL) 물량, 전국 = 시장 합, 출하지역(국산) 물량 = 시세 물량.
  - 소매가 < 도매가인 날 0 (소매가 ÷ 도매가 1.8~5.0배).
- **찾은 오류 — 원장 원본의 무게 입력 실수:**
  - 감귤 '800kg 상자' 211t 11원/kg, 열무 '60,201kg 상자', 느타리 '200kg 상자' 250t 3원/kg.
  - 깐마늘 46.8t 50원/kg 이 매일 같은 값으로 들어감.
  - 감자 '0.1kg 상자' 0.5kg 98만 원/kg, 배추 '기타' 0.01kg 상자.
- **고친 방법:** `build_tables.py` 의 `drop_entry_errors` 를 쓴다.
  - 같은 달, 같은 품목·품종의 **금액 가중 중앙값**과 비교한다. 거래가 10건 미만인 품종은 품목 값과 비교한다.
  - 1/10 미만이거나 10배를 넘는 줄은 뺀다.
  - 금액으로 무게를 매기는 이유: 이런 실수는 무게만 틀리고 금액은 맞아서, 틀린 줄이 기준값을 끌고 가지 못한다.
  - 빠지는 몫: 물량의 0.3~0.6%, 금액의 0.05~0.1%.
- **규칙을 고른 과정 (사후에 고친 것도 적음):**
  1. 처음엔 품목 중앙값으로 비교했다. 그랬더니 자색무·호부추·무말랭이처럼 원래 비싼 품종이 통째로 빠져서 품종 단위로 바꿨다.
  2. 품종 중앙값으로 바꾸자, 배추 '기타'의 0.01kg 상자 줄들이 중앙값을 1만 원으로 끌어올려 정상 배추가 빠졌다. 그래서 금액 가중 중앙값으로 바꿨다.
- **알려진 부작용:** 진짜 거래일 수 있는 아주 싼 줄도 빠진다. 예: 2026-06 사과, 가공용으로 보이는 300원/kg 줄 = 그 달 사과 물량의 약 4%.
- **남겨 둔 것 (오류 아님 또는 10배 안):**
  - 추석 뒤 애호박 하루 900t·1,000원 (진짜 거래).
  - 창원팔용 피망 2kg 상자 3만 원 (무게 실수로 보이지만 10배 안, 하루 2~10kg).
  - 만감 단위 물량 > 만감 품목 물량: 감귤 코드의 천혜향·레드향·황금향을 만감 단위로 옮긴 v3b 정의 때문.
- **DB 다시 넣기:** 없어진 줄이 DB 에 남지 않게 표를 비우고 bat 을 다시 실행한다.
  - `docker compose exec db psql -U postgres -d farmdb -c "TRUNCATE price_daily, price_origin_daily, price_unit_daily, market_factor, price_index_daily"`

## 시세 기간을 2020-01 부터로 늘림 (11-10)
- **기간:** 도매 시세 3표(`price_daily` · `price_origin_daily` · `price_unit_daily`)를 2020-01-01 ~ 2026-11-03 으로 다시 만듦 (예전 2025-01~). 원장 월별 원본 → `tools/import_ledger_csv.py` 로 하루 파일 2,193개 → `tools/build_prices_chunk.py` 로 4달씩 → `hist/price_all.csv` 를 `price_daily`(ALL)에서 다시 만든 뒤 `build_tables.py --since 2020-01-01 --only price_index_daily market_factor`
- **행 수:** price_daily 875만 · price_origin_daily 877만 · price_unit_daily 31.6만 · price_index_daily 16,601 · market_factor 17,133 (CSV 합계 약 1.1GB)
- **새로 찾은 오류 — 같은 날 자료가 통째로 두 번 들어간 법인:** 원본 점검표(`01_원본/경매원장_공영_원본/00_점검.csv`)의 "완전 중복 줄"이 2020-01·02, 2024-04·05 등에 몰려 있음. `build_tables.py` 의 `drop_double_feeds` 로 뺀다.
  - 규칙: 하루 파일 안에서, 26칸이 모두 같은 줄이 그 날 그 법인 줄의 20% 이상이면 그 법인은 "통째 중복"으로 보고 두 번째 줄부터 뺀다. 20% 미만이면 같은 값의 진짜 거래일 수 있어 그대로 둔다.
  - 점검표와 비교: 2024-04 58,847 ↔ 뺀 줄 58,613 · 2024-05 16,949 ↔ 16,652 · 2020-01 9,424 ↔ 9,242 · 2020-02 6,673 ↔ 6,432. 2024-06 은 점검표 366줄이 흩어져 있어 0줄 (20% 미만).
  - 참고: 2025-05 는 법인·날 단위 중복 비율이 0.05 이상인 곳이 없음 (정상 달에는 거의 안 걸림)
- **점검 (연도별, 3표) — 구조는 모두 통과:** 열쇠 중복 0, 빈칸 0, 단가 0 이하 0, 등급별 물량 합 ≤ 평균(ALL), 단가 = 금액 ÷ 물량(반올림 차이 1원 넘는 줄은 아주 작은 물량에서만 연 100~350줄)
- **알아 둘 것 (고치지 않음):**
  - 물량이 0.05kg 미만이라 `volume_kg` 이 0.0 으로 적힌 줄이 몇 개(연 0~23줄). 단가는 반올림 전 값으로 계산돼 맞음
  - 최저가(물량 아래 10%) > 평균가인 줄 약 1.7%, 최고가(위 10%) < 평균가 약 3%. 거래가 2~3건뿐인 날에 생기는 계산 방식의 특징 (오류 아님)
  - 전국 평균이 그 품목 중앙값의 10배를 넘거나 1/10 미만인 날 23일. 대부분 4월 하우스 복숭아(5~7만 원/kg, 하루 3~40kg)처럼 진짜로 보임. 2020-03-04 옥수수(3kg, 13만 원/kg — '0.3kg 개' 무게 입력 실수)는 그 달 옥수수 거래가 거의 이 줄뿐이라 `drop_entry_errors` 가 못 거름
- **DB 다시 넣기:** 위의 TRUNCATE 후 bat 다시 실행 (행이 약 4배라 몇 분 더 걸림)

## 아직 가짜·빈칸인 것
소매가는 22품목만(배추·무·사과처럼 '포기·개' 단위 품목은 빈칸), 지수 카드, AI 예측, 작물 추천 예상가. 출하지역 표의 최고·최저는 표에 없어 빈칸.
