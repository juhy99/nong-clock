# 팜비드 일일 수집 · DB 적재 (v3, 2026-11-06)

팜비드(농클락) DB 테이블 설계안(1106 수정본) 기준으로 **매일 들어오는 자료를 받아 → 테이블 모양 CSV로 만들고 → PostgreSQL에 넣는** 프로그램이다.
품목·품종은 팀 v3 기준(50품목, 예측 단위 326개)만 쓴다.

```
collect.py      매일 받기                      → data/raw/<자료>/ , 날씨는 data/weather/
weather/        팀 날씨 수집기(nong-clock collector/weather) 그대로 — ASOS·AWS·농업기상·단기·중기예보·장기전망 + 기상 통합 전처리
build_tables.py 테이블 모양으로 바꾸기        → data/tables/<테이블>.csv
load_db.py      PostgreSQL 에 넣기(같은 키면 덮어쓰기)
schema.sql      표 만들기 (설계안 19개 + 예측 입력 5개 = 24개)
policy/         팀 정책 수집기 그대로 (농식품부·aT 보도자료·공고)
ref/            기준표 (시·도, 시장, 품목 50, 예측 단위 326, 등급표, ASOS 지점→시·도, KAMIS 품목 연결, 특보구역)
API_목록.md     받아야 하는 API · 신청 방법 · 어떤 표를 채우는지
```

**날씨는 팀 수집기와 하나로 합쳤다(2026-11-06).** `weather/` 폴더가 nong-clock `collector/weather` 그대로이고, `collect.py weather`·`collect.py fcst`가 그 `run.py`를 부른다.
바꾼 곳은 `weather/run.py` 잠금 한 군데(윈도에서도 돌게 fcntl 없으면 msvcrt). 날씨 자세한 설명·호출 수·넘겨받을 파일은 `weather/README.md`.
키 이름이 같아서(`KMA_APIHUB_KEY`, `DATA_GO_KR_KEY`) 이 폴더 `.env` 하나로 둘 다 돈다. 날씨 자료는 `data/weather/`(팀 수집기의 DATA_DIR).

## 처음 한 번

1. Python 3.10 이상. `pip install -r requirements.txt`
2. `.env.example` 을 `.env` 로 복사하고 인증키를 채운다 (발급 방법은 `API_목록.md`). **.env 는 깃에 올리지 않는다** (.gitignore 에 있음)
3. 연결 시험: `python collect.py test` (또는 `1_연결시험.bat`) → 9개(auction kamis warning holiday fcst sanji at_resv fx garak_inout) 모두 ‘성공’인지 확인
4. DB 표 만들기: `python load_db.py --init` (접속 정보는 .env 의 PG…)
5. 과거 채우기 (둘 중 하나)
   - 받아 둔 경매원장을 옮기기(빠름): `python tools/import_ledger_csv.py <경매원장_공영도매시장\월별CSV 폴더> 202001 202611`
   - API로 새로 받기(며칠 걸림): `python collect.py auction --start 2020-01-01`
   - 날씨: `python collect.py weather --backfill` (ASOS 2015~·AWS 1997~·농업기상 2015~) 뒤 `python collect.py weather`(전처리까지)
     평년값(1991~2020)은 ASOS 1991~2014 원본 zip을 `data/weather/integrated/01_원본/ASOS/`에 넣어야 나온다 (weather/README 8번)
   - 예보 DB 이어 쓰기: PC의 `단기중기예보_수집기\data\진행상태.sqlite3` → `data/weather/raw/fcst/` (API가 최근 24시간분만 줘서 다시 못 받음)
   - 특보: `python collect.py warning --start 2020-01-01`
   - 그다음 `python build_tables.py --since 2020-01-01` → `python load_db.py`

## 매일

```
python collect.py daily      # 11가지: 공영도매·KAMIS·특보·날씨·예보·특일·산지공판장·가락 반입·aT 출하예약·환율·정책. PC를 며칠 껐으면 마지막 받은 날부터 이어받음
python build_tables.py       # 최근 14일만 다시 만듦
python load_db.py            # upsert
python collect.py fcst       # 예보만 — 3시간마다 따로 (02·05·…·23시 20분)
```
Windows: `2_매일_실행.bat` + `4_매일_자동실행_등록.bat`(매일 07:40) + `5_예보_3시간마다_등록.bat`
리눅스·도커: `run_daily.sh` 안의 cron 두 줄

**자료 올라오는 시점:** 공영도매 정산가격은 전날까지. 주말·월요일 거래분은 화요일에 대부분 올라온다 → 최근 7일의 ‘자료없음’은 매일 다시 확인한다. KAMIS 는 아침엔 ‘-’ 가 많아 최근 21일을 다시 받는다(오후에 한 번 더 돌리면 오늘 값이 찬다).

## 만들어지는 표

| 표 | 내용 | 출처 |
|---|---|---|
| region · market · item · index_group · variety_unit · grade_map | 기준표 | ref/ (+팀 shared/items.json·markets.json) |
| price_daily | 날짜 × 시장(+전국 'national') × 품목 × 등급(SPECIAL·HIGH·MID·LOW·ALL): 물량·금액·단가, 최고·최저 = 물량 가중 p90·p10 | 공영도매 정산가격 |
| price_origin_daily | 같은 것 × 출하 시·도 (수입은 origin_region_id 0) | 〃 |
| price_unit_daily | 날짜 × 예측 단위(326): 전국·국산 | 〃 + ref/variety_unit_code |
| price_index_daily | 품목 단가 ÷ 직전 365일 평균 × 100 을 묶음 안에서 평균 (평소 = 100) | price_daily 기록(data/hist) |
| market_factor | 품목 × 시장 × 달: 시장 단가 ÷ 전국 단가 중앙값(최근 3년, 10일 이상). 시장별 예측 = 전국 예측 × factor | 〃 |
| retail_price_daily | 날짜 × 품목 소매가 원/kg (상품 우선, kg·g 단위만) | KAMIS |
| weather_daily | 날짜 × 시·도: ASOS+AWS+농업기상 관측소 평균 (wind = 최대풍속) | 팀 날씨 `날씨_대통합_일별.csv` 시도_일 |
| weather_normal | 시·도 × 월·일 평년(1991~2020, 앞뒤 3일): 평균·최고·최저기온, 강수 | 〃 평년_ 열 |
| weather_warning_daily | 날짜 × 시·도 × 특보: 수준(1 주의보·2 경보·3 중대경보), 걸린 구역 비중 | 특보 이력 |
| weather_region_now | 시·도 오늘 날씨 + 농사 안내 문구 (시·도 안 시군구 격자 모아서) | 팀 예보 DB 최근 발표 |
| holiday | 공휴일 + 도매시장 휴장(설·추석, 지난 날은 원장 거래 없던 날) | 특일 정보 |
| producer_price_daily | 날짜 × 산지공판장(+전국) × 품목: 물량·금액·단가 | 산지공판장 정산 |
| garak_inout_daily | 날짜 × 경매전/후 × 가락 품목: 반입 kg (50품목 연결은 36개, 나머지 item_code '-') | 서울 열린데이터 |
| shipment_reservation_daily | 출하예정일 × 시장 × 품목 × 품종: 예약 kg, 받은 시각 | aT 출하예약 |
| fx_daily | 날짜 × 통화: 매매기준율 | ECOS |
| policy_doc | 보도자료·공고 제목·주소·날짜(게시일→발표일시, 없으면 비움)·받은 시각 | 팀 정책 수집기 |
| collect_log | 수집·적재 기록 (관리자 › 데이터 수집 현황) | data/log |

검증(조민철 PC, 2026-11-04 원장 + 시험 자료로 PostgreSQL 16 적재 두 번 — 두 번째도 행 수 같음): price_daily 전국 단가·물량이 NongClock 26번 원장 집계와 48품목 모두 일치(비율 0.999~1.001), p10·p90 도 일치. 예측 단위에 들어간 국산 물량 99.4~99.7%.

가락 경매전·후 반입 ÷ 같은 날 원장 가락(110001) 물량: 중앙값 0.998(경매전)·1.015(경매후).

## 안 하는 것 (팀 쪽)
- 뉴스(news_article): 팀 `collector/news` (네이버 API, 1시간마다)
- 회원·게시판·알림·신고·경매 표: 팀 `db/init/farm_table.sql`
- 예측값(forecast_daily): 예측 스크립트가 따로 넣는다 (이 수집 뒤에 돌리면 됨)

## ref/ 다시 만들기 (v3 단위가 바뀔 때, 조민철 PC)
`python tools/make_ref.py <E:\농산물 프로젝트\분석용> <C:\finalproject\nong-clock> <관측지점_마스터.csv> <특보구역 W04 원본>`
