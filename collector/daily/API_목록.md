# 팜비드 일일 수집 — 받아야 하는 API (2026-11-06)

DB 테이블 설계안(1106 수정본) 기준. **키는 각자 발급**해서 `.env`에 넣는다(`.env.example` 참고). 키를 코드·깃에 올리지 않는다.

## 0. 키별 신청 체크리스트 (2026-11-06 각 사이트에서 확인)

키 6곳 7개. **API허브와 data.go.kr은 API(서비스)마다 따로 [활용신청]** 해야 한다. 같은 키라도 신청 안 한 API는 인증 오류.

| 사이트 | `.env` 이름 | 신청할 것 (사이트에 적힌 이름 그대로) | 수집기 |
|---|---|---|---|
| 농식품 공공데이터포털 data.mafra.go.kr | `MAFRA_API_KEY` | 인증키 1개 + 데이터 2개 각각 [오픈 API 신청]:<br>① 전국 공영도매시장 정산정보 › 도매시장 정산 가격 정보 (data_id 20240625000000002459, Grid_..653_1)<br>② 도매시장 산지공판장 정산 가격 (data_id 20240625000000002467, Grid_..660_1) | auction · sanji |
| KAMIS kamis.or.kr | `KAMIS_KEY` `KAMIS_ID` | 마이페이지 › Open-API 신청 1번 (키 + 요청자 ID) | kamis |
| 기상청 API허브 apihub.kma.go.kr | `KMA_APIHUB_KEY` | **5개**, 메뉴 위치 그대로:<br>① 지상관측 › 종관기상관측(ASOS) › 1.4 일자료(기간 조회) `kma_sfcdd3.php`<br>② 지상관측 › 방재기상관측(AWS) › 4.1 지상 및 AWS 일통계 요소별 조회 `sfc_aws_day.php`<br>③ 지상관측 › 지상관측 지점정보 › 1.1.1 지상 `stn_inf.php`<br>④ 예특보 › 기상특보 › 1.1 특보구역 `wrn_reg.php`<br>⑤ 예특보 › 기상특보 › 1.2 특보자료 `wrn_met_data.php` | weather · warning |
| 공공데이터포털 data.go.kr | `DATA_GO_KR_KEY` | **5개** (모두 자동승인):<br>① 15084084 기상청_단기예보 조회서비스 (개발 10,000회/일)<br>② 15059468 기상청_중기예보 조회서비스 (10,000)<br>③ 15078057 농촌진흥청 국립농업과학원_농업기상 기본 관측데이터 조회 (**1,000**)<br>④ 15012690 한국천문연구원_특일 정보 (10,000)<br>⑤ 15141813 한국농수산식품유통공사_도매시장 전자송품장 출하예약정보 (10,000) | weather · fcst · holiday · at_resv |
| 서울 열린데이터광장 data.seoul.go.kr | `SEOUL_OPENAPI_KEY` | 일반 인증키 1개 (서비스별 신청 없음). 기존 가락 반입물량 수집기 키를 그대로 써도 됨 | garak_inout |
| 한국은행 ECOS ecos.bok.or.kr | `ECOS_API_KEY` | 인증키 1개 (통계표 731Y001) | fx |
| (키 없음) | — | 날씨누리 장기전망 PDF, 농식품부·aT 보도자료 | weather · policy |

- data.go.kr 은 승인 뒤 바로 안 될 수 있음(1~2시간). 디코딩(Decoding) 키를 넣는다.
- 2026-11-06 연결시험: kamis · warning(④⑤) · holiday 성공 / auction 실패 ‘INFO-100 인증키가 유효하지 않습니다’ → `.env` 의 MAFRA 키를 기존 수집기에서 쓰던 키로 다시 넣을 것.

## 1. 이 수집기(`collect.py`)가 매일 쓰는 API

| # | 자료 | 제공처 · 신청 | 인증키 (`.env` 이름) | 주소 | 주기 · 시점 | 채우는 테이블 |
|---|---|---|---|---|---|---|
| 1 | 공영도매시장 정산가격(시장·품목·품종·등급·산지 건별) | 농림축산식품 공공데이터포털 data.mafra.go.kr → 회원가입 → 인증키 발급 → ‘전국 공영도매시장 정산정보(도매시장 정산 가격 정보)’ 활용신청 | `MAFRA_API_KEY` | `http://211.237.50.150:7080/openapi/{키}/json/Grid_20240625000000000653_1/{시작}/{끝}?SALEDATE=YYYYMMDD&WHSALCD=시장코드` (한 번에 1,000행) | 매일, **전날까지**. 월요일 자료는 화요일에 올라오는 일이 많아 최근 7일의 ‘자료없음’은 다시 확인 | price_daily · price_origin_daily · price_unit_daily · price_index_daily · market_factor · holiday(휴장 판단) |
| 2 | KAMIS 일별 부류별 도·소매 가격 | KAMIS(www.kamis.or.kr) → 회원가입 → 마이페이지 Open-API 신청 → 인증키·요청자 ID | `KAMIS_KEY`, `KAMIS_ID` | `https://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList&p_product_cls_code=01(소매)/02(도매)&p_item_category_code=100·200·300·400&p_regday=YYYY-MM-DD` | 매일 오후(아침에는 값이 ‘-’인 날이 있어 최근 21일 다시 받음) | retail_price_daily |
| 3 | 날씨 관측 3종: ASOS 일자료 `kma_sfcdd3.php` · 지점정보 `stn_inf.php` · AWS 일통계 `sfc_aws_day.php` (팀 날씨 수집기) | 기상청 API허브 apihub.kma.go.kr → 회원가입 → API마다 활용신청 → authKey | `KMA_APIHUB_KEY` | `https://apihub.kma.go.kr/api/typ01/url/…` | 매일, 전날까지 | weather_daily · weather_normal |
| 3-2 | 농업기상 기본 관측 (팀 날씨 수집기) | 공공데이터포털 15078057 ‘농업기상 기본 관측데이터 조회’ | `DATA_GO_KR_KEY` | `/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherMonDayList3` | 매일 | weather_daily |
| 4 | 기상특보 발표 이력 + 특보구역 | 기상청 API허브 → ‘기상특보 > 특·정보 자료’ 활용신청 (3번과 같은 키) | `KMA_APIHUB_KEY` | 이력 `…/url/wrn_met_data.php?wrn=A&reg=0&tmfc1=…0000&tmfc2=…2359&disp=1` · 구역 `…/url/wrn_reg.php?disp=1` | 매일 | weather_warning_daily · forecast_alert(재료) |
| 5 | 단기예보 15084084 · 중기예보 15059468 (팀 날씨 수집기) | 공공데이터포털 → 각각 활용신청 → 일반 인증키(Decoding) | `DATA_GO_KR_KEY` | `/1360000/VilageFcstInfoService_2.0/getVilageFcst` (시군구 격자 218곳) · `/1360000/MidFcstInfoService/getMidLandFcst·getMidTa·getMidFcst` | **3시간마다** (최근 24시간 발표분만 줌). 하루 약 1,820회 — 개발계정 한도 10,000회 안 | weather_region_now |
| 5-2 | 1·3개월 장기전망 (팀 날씨 수집기) | 날씨누리 PDF (키 없음) | — | `weather.go.kr/w/wnuri-fct/rest/weather/long-term.do` | 매일 확인 | 예측 입력 |
| 6 | 특일 정보(공휴일) | 공공데이터포털 → ‘한국천문연구원_특일 정보’ 활용신청 (5번과 같은 키) | `DATA_GO_KR_KEY` | `http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo?solYear=&solMonth=&_type=json` | 30일마다(올해·내년) | holiday |
| 7 | 산지공판장 정산(건별) | 1번과 같은 포털 ‘산지공판장 정산정보’ 활용신청 | `MAFRA_API_KEY` | 1번 주소에서 `Grid_20240625000000000660_1` | 매일, 최근 45일 다시 확인 (2026-09-03 뒤로 새 자료 없음) | producer_price_daily |
| 8 | 가락 경매전·후 반입물량 | 서울 열린데이터광장 data.seoul.go.kr → 인증키 신청 | `SEOUL_OPENAPI_KEY` | `http://openapi.seoul.go.kr:8088/{키}/json/GarakAuctionBefore·GarakAuctionAfter/{시작}/{끝}` (톤 단위, 부를 때마다 전체 목록) | 매일 (전체 다시) | garak_inout_daily |
| 9 | aT 도매시장 출하예약(전자송품장, 전국·품종) | 공공데이터포털 ‘한국농수산식품유통공사_전자송품장 출하예약’ 활용신청 (5번과 같은 키) | `DATA_GO_KR_KEY` | `http://apis.data.go.kr/B552845/katElectronicInvoice2/shipmentReservations2?cond[spmt_dt::EQ]=YYYY-MM-DD` | 매일, 지난 14일 + 앞으로 3일 (받은 시각 collected_at 저장) | shipment_reservation_daily |
| 10 | 환율(일별 매매기준율) | 한국은행 ECOS ecos.bok.or.kr → 인증키 신청 | `ECOS_API_KEY` | `https://ecos.bok.or.kr/api/StatisticSearch/{키}/json/kr/1/1000/731Y001/D/{시작}/{끝}` | 매일, 최근 10일 | fx_daily |
| 11 | 정부 수급정책 보도자료·공고 (팀 정책 수집기 `policy/`) | 농식품부·aT 누리집 (키 없음) | — | `policy/config.json` 의 목록 페이지 | 매일 (최근 3페이지) | policy_doc |

> 가락 **출하예약(접수물량)** 은 aT 9번에 가락시장도 들어 있어 따로 받지 않는다 (einvoice.garak.co.kr 은 robots.txt 로 자동수집을 막아 둠).
> 6번 특일 정보는 이 프로젝트에서 처음 쓰는 API라 **연결시험(`python collect.py test`)에서 확인**해야 한다. 1·2·4번은 NongClock 통합 수집기에서 매일 쓰는 주소·파라미터 그대로, 3·5번은 팀 날씨 수집기 그대로다.

## 2. 팀 수집기 중 이 묶음에 안 넣은 것

| 자료 | 위치 | 테이블 |
|---|---|---|
| 농업 뉴스 (네이버 뉴스 검색 API, 1시간마다) | nong-clock `collector/news` (`NAVER_CLIENT_ID`·`SECRET`) | news_article · news_item_tag |

(날씨 `collector/weather`는 이 묶음 `weather/`로 합쳤음)

## 3. 아직 안 붙인 것

| 자료 | 이유 |
|---|---|
| 가락 einvoice 출하예약 화면 | robots.txt 로 막힘 → aT 출하예약(9번)으로 대신 |
| 농업관측월보(KREI)·OASIS | robots 로 막힘, 수동 내려받기 |
| 통계청 재배면적, 관세청 수입량, 네이버 검색량, NMME | 연·월 단위 자료라 일일 수집 밖 (예측 스크립트 쪽) |

## 4. 수집 주기 요약

```
매일 아침(07:40 권장)  collect.py daily  → build_tables.py → load_db.py
  - (11가지) auction kamis warning weather fcst holiday sanji garak_inout at_resv fx policy
  - 공영도매 정산가격: 전날까지 (토·일·월 거래분은 화요일에 대부분 채워짐)
  - KAMIS: 오늘까지 (오후에 한 번 더 돌리면 오늘 값이 채워짐)
  - 날씨 관측·특보: 전날까지 / 예보: 3시간마다 따로
3시간마다           collect.py fcst (단기·중기예보)
처음 한 번          collect.py auction --start 2020-01-01 (또는 tools/import_ledger_csv.py 로 받아 둔 원장 옮기기)
                    collect.py weather --backfill → collect.py weather → build_tables.py --only weather_normal
```

## 5. 예측 모델에 들어가는 자료 (NongClock 모델 기준 — 사이트 표와 별개로 예측 스크립트가 읽음)

| 묶음 | 자료 | 받는 곳 | 주기 | 이 수집기 |
|---|---|---|---|---|
| 가격·물량(정답·입력) | 공영도매 정산가격(품종·등급·산지) | 1번 API | 매일 | ✔ |
| | 가락 반입량(8번), aT 출하예약(9번) | 1장 표 | 매일 | ✔ |
| 기상 | ASOS·AWS·농업기상 일자료 | 기상청 API허브·농진청 | 매일 | ✔ (weather/) |
| | 기상특보 | 기상청 API허브 | 매일 | ✔ |
| | 단기·중기예보, 1·3개월 전망 | 기상청 | 3시간·매일 | ✔ (weather/) |
| | NMME 계절예측 | NOAA | 매달 | ✗ |
| 공급 | 통계청 재배면적·생산량(작형·숙기) | KOSIS·보도자료 | 연 1~3회 | ✗ (발표일 다음 날부터 사용) |
| | 농업관측월보(재배·출하 전망) | KREI(수동 내려받기) | 매달 | ✗ |
| | 농업경영체 재배면적 | uni.agrix | 연 1회(4월) | ✗ |
| 수요·외부 | 환율(ECOS, 10번) | ECOS | 매일 | ✔ |
| | 수입량(관세청, 월), 네이버 검색량 | 각 API | 매달 | ✗ |
| 정책 | 정부 수급정책 보도자료(11번) | 농식품부·aT | 매일 | ✔ |
| 달력 | 명절·공휴일 | 특일 정보 | 연 1회 | ✔ |

> 가격은 모델의 정답으로만 쓰고 입력에는 넣지 않는다(프로젝트 규칙).
