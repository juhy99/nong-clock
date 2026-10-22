# 날씨 수집기 + 통합 전처리 (collector/weather)

PC(윈도)에서 돌리던 날씨 수집기 5개와 기상 통합 전처리를 리눅스 서버에서 돌리도록 옮긴 것입니다.
수집 로직은 원래 코드 그대로 두고 경로·키 읽기·오류 처리만 바꿨습니다(바꾼 점은 맨 아래).

| 서버 파일 | 원래 파일(PC) | 하는 일 |
|---|---|---|
| `collect_asos.py` | NongClock_ASOS_전국_수집_수정본.py | ASOS(종관) 일자료 |
| `collect_aws.py` | AWS_일자료_전국_빠른수집.py | AWS(방재) + ASOS 지점 일통계 5요소 |
| `collect_agri.py` | agri_weather.py | 농진청 농업기상 일자료 |
| `collect_fcst.py` | collect_fcst.py | 기상청 단기·중기예보 |
| `collect_longrange.py` | collect_longrange.py | 기상청 장기전망(1개월·3개월) PDF |
| `preprocess_weather.py` | 기상_통합_전처리.py | ASOS+AWS+농업기상 → 03_연결 |
| `build_weather_daily.py` | build_weather_daily.py | 03_연결 → 날씨_대통합_일별.csv |
| `run.py` | (새로 만듦, PC 전처리갱신.py의 기상 단계 일부) | 수집·전처리 실행, 기록, STOP 처리 |
| `wxcommon.py` | (새로 만듦) | 데이터 폴더, 키, 호출 수 세기, 종료 코드 |
| `ref/` | 시군구_좌표.csv, 중기구역.csv, 농업기상_설정.txt | 코드가 읽는 참고 파일 |

## 1. 설치

```bash
cd collector/weather
python3 -m pip install -r requirements.txt
cp .env.example .env      # 키 2개 채우기
mkdir -p data
```

- 키는 환경변수(또는 `.env`)에서만 읽습니다. 입력창은 없습니다. 이미 있는 환경변수가 `.env`보다 우선입니다.
- `KMA_APIHUB_KEY`: 기상청 API허브 키 (ASOS·AWS). 예전 이름 `KMA_AUTH_KEY`도 읽습니다.
- `DATA_GO_KR_KEY`: 공공데이터포털 일반 인증키(Decoding) (농업기상·단기·중기예보). Encoding 키를 넣어도 동작합니다.
- 키가 없는 수집은 오류로 기록하고 건너뜁니다.

## 2. 실행 명령

```bash
python3 run.py collect                                  # 수집 5개 전부
python3 run.py collect --only fcst                      # 단기·중기예보만
python3 run.py collect --only asos,aws,agri,longrange   # 관측·장기전망
python3 run.py preprocess                               # 기상 통합 전처리 → 날씨 대통합 일별
python3 run.py all --only asos,aws,agri,longrange       # 수집 다음 전처리
python3 run.py collect --backfill                       # 처음 1번: 과거 전체 (아래 6번 참고)
```

run.py가 각 수집기에 넘기는 값 (한국시간 기준):

| 이름 | 넘기는 인수 |
|---|---|
| asos | `--start 2015-01-01 --end <어제> --out data/raw/asos` |
| aws | `--start <어제가 속한 연도> --out data/raw/aws` (backfill: `--start 1997`) |
| agri | `--start <지난달> --end <이번 달> --out data/raw/agri` (backfill: `--start 2015-01`) |
| fcst | `--part all --times all --data data/raw/fcst` |
| longrange | `--part latest --output data/raw/longrange` |

- **ASOS 시작일은 반드시 2015-01-01** 입니다. 이 수집기는 준 기간으로 `ASOS_일자료_전국통합.csv`를 다시 만듭니다.
  이번 달을 시작일로 주면 통합 CSV가 한 달치로 덮어써집니다(PC에서 실제로 있었던 사고). 검증된 달은 건너뛰므로 호출은 늘지 않습니다.
- `preprocess`는 다음 순서로 실행합니다.
  1. 수집 결과를 `data/integrated/01_원본/`에 복사합니다. 새 파일이 예전보다 1% 넘게 작으면 덮어쓰지 않고 멈춥니다.
  2. 올해 캐시를 지웁니다(1월에는 작년 캐시도 지움).
     - `02_전처리/AWS/{연도}.csv`
     - `02_전처리/AWS/_좌표/{연도}.csv`
     - `link/_집계/{연도}_stat.json`
     - `site/_중간/sgg_{연도}.csv`
  3. `preprocess_weather.py --step all`을 실행합니다.
  4. `build_weather_daily.py`를 실행합니다.

## 3. 얼마나 자주 (cron 예시)

| 작업 | 주기 | 이유 |
|---|---|---|
| 단기·중기예보 (`--only fcst`) | **3시간마다, 단기 발표(02·05·08·11·14·17·20·23시) 20분 뒤** | API가 최근 24시간 발표분만 줌. 한 번 놓치면 다시 못 받음 |
| ASOS·AWS·농업기상·장기전망 | 하루 1번 | 일자료. 장기전망은 날씨누리에 지금 발표분만 있어 매일 확인 |
| 전처리 | 하루 1번, 수집 뒤 | `all` 명령으로 수집 다음에 바로 실행 |

```cron
CRON_TZ=Asia/Seoul
# 단기·중기예보
20 2,5,8,11,14,17,20,23 * * *  cd /경로/collector/weather && python3 run.py collect --only fcst >> data/cron.log 2>&1
# 관측 + 장기전망 수집 → 전처리 (매일 10:40)
40 10 * * *  cd /경로/collector/weather && python3 run.py all --only asos,aws,agri,longrange >> data/cron.log 2>&1
```

- 예보 실행 시각의 근거는 다음과 같습니다(`collect_fcst.py` 코드 기준).
  - 단기: 매번 "지금 − 15분" 이전 24시간 안의 발표 8번 중 DB에 없는 것만 받습니다(`--times all`).
    3시간마다 돌리면 발표마다 1번씩 받고, 한 번 실패해도 24시간 안의 다음 실행이 다시 받습니다.
  - 중기: 06·18시 발표를 "지금 − 30분" 기준으로 찾습니다. 06시분은 08:20 실행, 18시분은 20:20 실행에서 받습니다.
- **발표 시각 ≠ API 조회 가능 시각.** 발표 주기는 공식 자료로 확인됨(단기 02·05·08·11·14·17·20·23시, 중기 06·18시: [기상청 예보업무 안내](https://www.kma.go.kr/kma/biz/forecast02.jsp)).
  하지만 발표 후 몇 분부터 API에서 받을 수 있는지는 공식 문서에 없습니다([단기예보 API](https://www.data.go.kr/data/15084084/openapi.do)는 업데이트 주기 "실시간"으로만 표시).
  그래서 수집기는 발표 시각을 정확히 노리지 않고, 매 실행마다 **최근 24시간 안에서 DB에 없는 발표를 모두** 다시 조회합니다. 아직 비어 있으면(NO_DATA) 저장하지 않고 다음 실행에서 다시 받습니다.
  두 API 모두 최근 24시간분만 주므로([중기예보 API](https://www.data.go.kr/data/15059468/openapi.do): "최근 24시간 자료만 제공"), 24시간 안에 최소 1번은 성공해야 합니다. 3시간마다 실행이면 한 발표당 기회가 약 8번입니다.
- 관측자료를 몇 시에 돌려야 어제 자료가 다 들어오는지는 코드로 알 수 없습니다(**확인 필요**).
  10:40은 임의로 정한 시각입니다. 늦게 들어온 값은 다음 날 실행 때 이번 달·올해분을 다시 받으면서 채워집니다.
- 같은 수집기가 겹쳐 실행되면 뒤의 것이 최대 30분(`RUN_LOCK_WAIT` 초) 기다립니다. 그래도 안 끝나면 이번 실행은 건너뛰고 기록합니다.
  잠금은 `fcntl.flock`이라 프로세스가 죽으면 자동으로 풀립니다.

## 4. 원본이 저장되는 곳과 형태

데이터 폴더는 `DATA_DIR`(기본 `collector/weather/data`)입니다. DB 서버는 쓰지 않고, DB가 필요한 곳은 **SQLite 파일**(파이썬 내장 sqlite3)입니다.

| 폴더 | 원본 형태 | 그 밖의 결과 |
|---|---|---|
| `raw/asos/` | **파일**: `원본/YYYY-MM.txt.gz` (API 응답 원문, 월 단위) | `월별CSV/YYYY-MM.csv`·`.meta.json`(검증·이어받기), `ASOS_일자료_전국통합.csv`, `관측소/`, 검증 CSV·JSON |
| `raw/aws/` | **파일**: `원본/{요소}_{연도}.txt.gz` (요소 5개 × 연도, 키는 `[KEY]`로 가림) | `요소별/*.csv`, `AWS_ASOS_일자료_전국통합.csv`, `수집현황.csv`, `수집요약.json` |
| `raw/agri/` | **SQLite** `진행상태.sqlite3`: 표 `jobs`(월별 상태), `rows`(API 항목 1개 = JSON 1행) | `월별CSV/`, `농업기상_일자료_통합.csv`, `관측지점_목록.csv` |
| `raw/fcst/` | **SQLite** `진행상태.sqlite3`: 표 `raw(kind, issue, point, n, body, got)`, body = 응답 JSON gzip 압축 | `01_단기예보_일별요약.csv` ~ `04_중기전망_문장.csv`, `05_최신현황.json` |
| `raw/longrange/` | **파일**: `pdf/1개월·3개월/<지점>/*.pdf` | `text/`, `csv/01_장기전망_지역별_확률.csv` 등, `수집로그.csv` |
| `integrated/` | 전처리 입력 복사본 `01_원본/`, `02_전처리/`, `전처리_점검.json` | |
| `link/` | (= PC의 03_연결) | `일자료_연도별/{연도}.csv`, `시도별_일기상.csv`, `시군구별_월기상.csv`, `관측지점_마스터.csv` 등 |
| `site/` | | `날씨_대통합_일별.csv`, `점검.json`, `_중간/` |
| (최상위) | | `collect_log.json`, `preprocess_log.json`, `logs/`, `.locks/`, `STOP_*` |

## 5. 하루 호출 수 (위 cron 기준, 재시도 제외)

| API | 하루 호출 | 계산 (코드 기준) |
|---|---|---|
| API허브 ASOS 일자료 `kma_sfcdd3.php` | **1** | 한 달을 1번에 받음(stn=0, 쪽 나눔 없음). 끝 날짜가 바뀐 이번 달만 다시 받음 |
| API허브 지점정보 `stn_inf.php` | **1** | `관측소/관측지점_{어제}.csv`가 날마다 새 파일이라 1번 |
| API허브 AWS 일통계 `sfc_aws_day.php` | **5** | 요소 5개(최고·최저기온, 강수량, 최대풍속, 최대순간풍속) × 올해 1년치 1번 |
| 공공데이터포털 농업기상 `getWeatherMonDayList3` | **최대 약 8** (매월 1·2일은 최대 약 9) | 이번 달 쪽수 = ⌈지점 수 × 날짜 수 ÷ 1000(Page_Size)⌉. 233지점(PC 문서의 누적 지점 수) × 31일 = 7,223행 → 8쪽. 매월 1·2일에는 지난달도 다시 받음. 실제 운영 지점 수는 **확인 필요** |
| 공공데이터포털 단기예보 `getVilageFcst` | **1,744** | 격자 218개 × 발표 8번. `ref/시군구_좌표.csv` 249행 중 좌표가 있는 225행 → 5km 격자 중복 제거 218개. 격자마다 1쪽(numOfRows=1500) |
| 공공데이터포털 중기 육상 `getMidLandFcst` | **20** | 구역 10개 × 발표 2번(06·18시) |
| 공공데이터포털 중기 기온 `getMidTa` | **54** | 도시 27개 × 발표 2번 |
| 공공데이터포털 중기 전망 `getMidFcst` | **2** | 지점 1개(108) × 발표 2번 |
| 날씨누리 장기전망 (키 없음) | **22 + 새 PDF 수** | 목록 2종(1개월·3개월) × 지역 11개 = 22. 새 발표가 있는 날만 PDF를 더 받음(1개월: 매주 목요일, 3개월: 매월 23일. 코드 주석 기준) |

합계는 API허브 7회, 공공데이터포털 약 1,828회(단기 1,744 + 중기 76 + 농업기상 약 8)입니다.

- 실패한 요청도 1번으로 셉니다. `collect_log.json`의 `calls`는 재시도까지 포함한 실제 요청 수입니다.
- 재시도 횟수: ASOS·AWS 최대 4번, 예보·장기전망 최대 3번, 농업기상은 재시도 없이 다음 실행 때 다시 받습니다.
- 처음 1번(`--backfill`) 호출 수
  - ASOS: 1 + 142개월(2015-01 ~ 2026-10) = 143
  - AWS: 5 × 30년(1997 ~ 2026) = 150
  - 농업기상: 142개월 × 월별 쪽수 (**확인 필요**)
- 단기예보는 격자마다 1쪽(1500행)만 받고 totalCount와 비교하지 않습니다. 발표 1번이 1500행을 넘는지는 **확인 필요**입니다.
  10-22 11시 발표는 4~5일치, 카테고리 14개였습니다.
- 공공데이터포털 하루 트래픽 한도: 단기예보·중기예보 API 모두 개발계정 10,000회(운영계정은 활용사례 등록 후 증가 신청, 각 API 페이지 기준). 단기 1,744회는 그 안에 듭니다. API허브·농업기상 한도는 **확인 필요**입니다.

## 6. 신청해야 할 API (서버 계정)

**기상청 API허브** (apihub.kma.go.kr) — 키 `KMA_APIHUB_KEY`. API마다 활용신청이 따로 필요합니다.
1. 지상관측 > 종관기상관측(ASOS) > 일자료(기간 조회) — `/api/typ01/url/kma_sfcdd3.php`
2. 지상관측 지점정보 조회 — `/api/typ01/url/stn_inf.php` (실패해도 일자료는 계속 받음, 지점명·좌표만 비음)
3. 지상 및 AWS 일통계 – 요소별 조회 — `/api/typ01/url/sfc_aws_day.php`

**공공데이터포털** (data.go.kr) — 키 `DATA_GO_KR_KEY`
4. 농촌진흥청 국립농업과학원 「농업기상 기본 관측데이터 조회」 — 데이터셋 **15078057**
   - 주소: `/1390802/AgriWeather/WeatherObsrInfo/V3/GnrlWeather/getWeatherMonDayList3`
   - 주소가 바뀌면 `ref/농업기상_설정.txt`를 고칩니다.
5. 「기상청_단기예보 ((구)_동네예보) 조회서비스」 — 데이터셋 **15084084** — `/1360000/VilageFcstInfoService_2.0/getVilageFcst`
6. 「기상청_중기예보 조회서비스」 — 데이터셋 **15059468** — `/1360000/MidFcstInfoService/getMidLandFcst`, `getMidTa`, `getMidFcst`

**날씨누리** (weather.go.kr) — 키가 없습니다. 장기전망(1개월 매주 목요일, 3개월 매월 23일경)은 OpenAPI가 아니라 PDF입니다. 공공데이터포털의 「기상청_1개월전망」([15050697](https://www.data.go.kr/data/15050697/fileData.do))도 PDF 파일데이터(기관 사이트에서 내려받기)이고, 수집기는 날씨누리 목록에서 PDF를 받습니다. `/w/wnuri-fct/rest/weather/long-term.do`, `/w/repositary/xml/fct/mon/{파일}`

### AWS(방재 지점) 자료는 어디서 오나
- `collect_aws.py`는 공공데이터포털이 아니라 **기상청 API허브의 `sfc_aws_day.php`**(지상 및 AWS 일통계 – 요소별 조회, `stn=0` 전 지점)에서 받습니다.
- **키는 공공데이터포털 키와 별개**입니다. ASOS와 같은 API허브 키(`KMA_APIHUB_KEY`)를 쓰지만, 이 API는 API허브에서 따로 활용신청해야 합니다.
- 받는 요소는 최고·최저기온, 강수량, 최대풍속, 최대순간풍속 5개입니다. 평균기온·습도·일조는 이 API에 없습니다.
- 응답에는 ASOS 지점도 들어 있습니다.
- PC 폴더의 `먼저읽기_실행방법.txt`는 이 코드가 아니라 예전 다른 수집기(방재기상월보 `getDailyAwsData`/`getAwsStnLstTbl`, aws_download.py)의 설명이어서 넣지 않았습니다.

## 7. 실패 처리

- **종료 코드**
  - 0: 정상
  - 1: 실패. 다음 실행에서 이어받음
  - 2: 키 없음
  - 3: 인증 오류
  - 4: 호출 한도 초과
- **인증 오류(3)**: 각 수집기는 다음 경우 바로 멈추고 3으로 끝납니다.
  - HTTP 401·403
  - 공공데이터포털 결과코드 20·30·31·32·33 (SERVICE_KEY_IS_NOT_REGISTERED, 기한만료, 미등록 IP 등)
  - API허브 응답의 인증 오류 문구

  그러면 run.py가 `data/STOP_KMA_APIHUB_KEY` 또는 `data/STOP_DATA_GO_KR_KEY` 파일을 만들고 사유를 적습니다.
  이 파일이 있는 동안 그 키를 쓰는 수집은 전부 건너뜁니다(같은 실행 안의 나머지 수집도 포함).
  **키나 활용신청을 고친 뒤 STOP 파일을 지우면** 다음 실행부터 다시 수집합니다.
- **호출 한도(4)**: HTTP 429나 결과코드 22이면 STOP 파일을 만들지 않고 다음 실행 때 다시 시도합니다.
- **일시 오류**(시간초과, 5xx 등): `errors`에 기록하고 다음 실행에서 이어받습니다. 이미 받은 달·연도·발표분은 다시 받지 않습니다.
- **중간에 죽었을 때**: 원본 파일은 임시 파일에 쓴 뒤 교체하고, DB는 SQLite 트랜잭션을 씁니다. 그래서 다음 실행에 영향이 없습니다.
- **수집 기록** `data/collect_log.json`: 최근 100번을 남깁니다.
  ```json
  {"runs":[{"finished_at":"2026-10-22T10:52:01+09:00","ok":true,"added":0,"calls":0,"errors":[],
            "started_at":"…","sources":{"asos":{"ok":true,"added":…,"calls":…,"exit":0,"errors":[],"log":"…","seconds":…}}}]}
  ```
  - `calls`: 각 수집기가 `urllib.request.urlopen`을 부른 횟수입니다. 수집기 마지막 줄 `##STATS {...}`에서 읽습니다.
  - `added`는 수집기마다 세는 방법이 다릅니다.

    | 수집기 | `added` |
    |---|---|
    | asos | `ASOS_일자료_전국통합.csv` 행 수(실행 후 − 실행 전) |
    | aws | 다시 받은 연도 파일 행 수(새로 − 예전) |
    | agri | SQLite `rows` 행 수 증가분 |
    | fcst | 새로 저장한 응답 수(발표 × 격자/구역) |
    | longrange | 새로 받은 PDF 수 |
- 전처리 기록은 `data/preprocess_log.json`에 같은 모양으로 남습니다. `added`는 `날씨_대통합_일별.csv` 행 증가분입니다.
- 실행 화면 전체는 `data/logs/`에 남고, 30일이 지나면 지웁니다.

## 8. 따로 넘겨받아야 하는 것 (서버에서 다시 받을 수 없음)

| 무엇 | PC에서 | 서버에 둘 곳 |
|---|---|---|
| **단기·중기예보 원본 DB** (2026-10-21 이후). API가 최근분만 줘서 다시 못 받음 | 예보 수집기 폴더 `data/진행상태.sqlite3` | **`data/raw/fcst/진행상태.sqlite3`** (같은 표 구조라 그대로 이어서 쌓임) |
| 장기전망 PDF. 날씨누리는 지난 PDF를 지움 | 장기기상전망_수집기 `data/pdf/` | `data/raw/longrange/pdf/` |
| ASOS 1991~2014 (수집기 없음, 파일) | 기상_통합 `01_원본/ASOS/asos_일자료_통합_1991_2025.zip` | `data/integrated/01_원본/ASOS/` (없으면 2015년부터만 나오고 평년(1991~2020) 값이 비거나 불완전함) |
| (선택) AWS 지점 주소 | 기상_통합 `01_원본/AWS/연월별_전체지점목록.csv`, `AWS_지점정보_원본.txt` | `data/integrated/01_원본/AWS/` (없으면 주소 없는 AWS 지점은 가장 가까운 지점의 시도·시군구로 추정. 이 두 파일을 만든 수집기는 **확인 필요**) |
| (선택) ASOS 지점명 보완표 | `ASOS_관측지점_참고_97개.csv` | `ref/` (없어도 됨) |

ASOS·AWS·농업기상은 `run.py collect --backfill`로 다시 받을 수 있습니다. 호출을 아끼려면 PC 원본을 그대로 옮겨도 됩니다.

| 자료 | PC에서 | 서버에 둘 곳 |
|---|---|---|
| ASOS | 수집 폴더의 `원본/`, `월별CSV/`(meta 포함) | `data/raw/asos/` |
| AWS | `원본/*.txt.gz` | `data/raw/aws/원본/` |
| 농업기상 | `진행상태.sqlite3` | `data/raw/agri/` |

## 9. 원래 코드에서 바꾼 점

- **공통**
  - 고정 경로를 `DATA_DIR` 아래 폴더로 바꿨습니다.
  - getpass 입력창을 없애고 키는 환경변수에서만 읽습니다.
  - .bat 안내문을 지웠습니다.
  - `##STATS` 출력과 종료 코드 3·4를 넣었습니다.
  - truststore는 선택입니다(원래부터 없어도 동작).
- **ASOS**
  - 원래는 이번 달 원본(`원본/YYYY-MM.txt.gz`)이 있으면 끝 날짜가 바뀌어도 예전 원본을 다시 써서 새 날짜가 안 들어왔습니다.
    이제 meta의 기간이 다르면 새로 받습니다.
  - API허브 401·403은 재시도 없이 종료 코드 3으로 끝납니다.
  - 기본 끝 날짜를 고정값에서 한국시간 어제로 바꿨습니다.
- **AWS**
  - 원래는 있는 연도 파일을 건너뛰어 올해 파일이 갱신되지 않았습니다. 이제 "어제가 속한 연도" 파일은 매번 다시 받습니다(임시 파일 → 교체).
  - run.py는 시작 연도로 "어제가 속한 연도"를 넘깁니다. 1월 1일에 작년 12월 31일을 받기 위해서입니다.
  - 401·403일 때 원래는 종료 코드 0이었는데 이제 3입니다.
- **농업기상**
  - 원래는 이번 달만 매번 다시 받아서 지난달 마지막 날이 빠진 채 완료로 남을 수 있었습니다.
    이제 끝난 달은 "말일 + 2일 이후에 받은 기록"이 있어야 완료로 봅니다.
  - `--out`을 추가했습니다.
  - 429·결과코드 22는 한도 초과(4)로 구분합니다.
- **예보**
  - 원래는 빈 응답(NO_DATA)도 저장해서 다시 받지 않았습니다. 이제 저장하지 않고 다음 실행에서 다시 받습니다.
  - `--data`(저장 폴더)를 추가했습니다. 참고 파일은 `ref/`, 설정은 `ref/예보_설정.json`(선택)에서 읽습니다.
  - 인증 오류 판단에 결과코드를 씁니다.
- **장기전망**: 기본 폴더와 안내문을 바꿨습니다. 실패가 있으면 종료 코드 1로 끝납니다.
- **기상 통합 전처리**: `--link` 옵션을 추가하고 `--base` 기본값을 `data/integrated`로 바꿨습니다.
- **대통합 일별**: 기본 폴더를 `DATA_DIR/link`, `DATA_DIR/site`로 바꿨습니다.
- **run.py 캐시 삭제**: PC 전처리갱신.py가 지우던 3종에 `build_weather_daily`의 `_중간/sgg_{연도}.csv`를 더했습니다.
  지우지 않으면 올해 시군구 일별이 갱신되지 않습니다.
- **옮기지 않은 것**: PC 전처리갱신.py의 `02_전처리/06_기상`(merge_all.py) 단계와 다른 자료 단계.

## 10. 시험

```bash
python3 collect_asos.py --self-test                    # ASOS 파싱·저장·이어받기 (네트워크 없음)
python3 -m unittest tests/test_auth_stop.py -v         # 키 없음·401·403·결과코드 30 → STOP, 22 → 한도, 500 → 일시 오류
```
시험은 로컬 http.server를 띄우고 `KMA_APIHUB_BASE`, `DATA_GO_KR_BASE` 환경변수로 주소를 바꿔서 실행합니다(실제 API는 부르지 않음).
