-- 수집·시세·날씨 표 (팀 수집기 farmbid_daily/schema.sql 과 같은 내용, 2026-11-09 복사, 11-12 다시 맞춤).
-- DB 를 처음 만들 때 farm_table.sql(회원·게시판)과 같이 자동 실행된다. 수집기 load_db.py --init 도 같은 문(IF NOT EXISTS)이라 겹쳐도 괜찮다.
-- 표를 바꿀 때는 수집기 schema.sql 과 이 파일을 같이 고칠 것.

-- 팜비드 DB — 수집 자료가 들어가는 표 (설계안 1106 기준 + 점검에서 더한 market_factor · weather_normal)
-- 회원·게시판·알림·신고·경매 표는 팀 db/init/farm_table.sql 쪽 (여기는 수집·시세·날씨만)
-- PostgreSQL 15. 처음 한 번: psql -d farmdb -f schema.sql   (load_db.py --init 도 같은 일)

CREATE TABLE IF NOT EXISTS region (
    region_id   SMALLINT     PRIMARY KEY,
    name        VARCHAR(10)  NOT NULL,
    map_id      VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS market (
    market_code VARCHAR(10)  PRIMARY KEY,           -- 정산 자료 도매시장코드, 전국 = 'national'
    name        VARCHAR(20)  NOT NULL,
    region_id   SMALLINT     REFERENCES region(region_id),
    sigungu     VARCHAR(20),
    lat         NUMERIC(8,5),
    lon         NUMERIC(8,5),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS index_group (
    group_code  VARCHAR(20)  PRIMARY KEY,
    name        VARCHAR(20),
    emoji       VARCHAR(8),
    categories  TEXT[]
);

CREATE TABLE IF NOT EXISTS item (
    item_code   VARCHAR(30)  PRIMARY KEY,
    code4       CHAR(4)      NOT NULL UNIQUE,       -- 공영 품목코드 (대분류2+중분류2)
    name        VARCHAR(20)  NOT NULL,
    category    VARCHAR(10),
    index_group VARCHAR(20),
    emoji       VARCHAR(8),
    kamis_code  VARCHAR(10),
    sort_order  SMALLINT
);

CREATE TABLE IF NOT EXISTS variety_unit (
    unit_id        INT          PRIMARY KEY,
    unit_name      VARCHAR(40)  NOT NULL UNIQUE,
    item_code      VARCHAR(30)  REFERENCES item(item_code),
    unit_kind      VARCHAR(20),
    variety_codes  TEXT[],                         -- 공영 소분류(품종)코드
    variety_names  TEXT,
    months         SMALLINT[],                     -- 철로 나눈 단위만
    main_region_id SMALLINT     REFERENCES region(region_id),
    cultivation    VARCHAR(10),
    origin_type    VARCHAR(20),
    avg_volume_t   NUMERIC,
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS grade_map (
    source     VARCHAR(10),
    raw_grade  VARCHAR(20),
    grade      VARCHAR(8) NOT NULL,
    PRIMARY KEY (source, raw_grade)
);

CREATE TABLE IF NOT EXISTS holiday (
    date             DATE        PRIMARY KEY,
    name             VARCHAR(30),
    is_market_closed BOOLEAN
);

CREATE TABLE IF NOT EXISTS price_daily (
    date        DATE         NOT NULL,
    market_code VARCHAR(10)  NOT NULL REFERENCES market(market_code),
    item_code   VARCHAR(30)  NOT NULL REFERENCES item(item_code),
    grade       VARCHAR(8)   NOT NULL,             -- SPECIAL HIGH MID LOW ALL
    volume_kg   NUMERIC,
    amount_won  NUMERIC,
    price       INT,
    price_high  INT,
    price_low   INT,
    PRIMARY KEY (date, market_code, item_code, grade)
);
CREATE INDEX IF NOT EXISTS idx_price_daily_look ON price_daily (item_code, market_code, grade, date DESC);

CREATE TABLE IF NOT EXISTS price_origin_daily (
    date             DATE        NOT NULL,
    market_code      VARCHAR(10) NOT NULL REFERENCES market(market_code),
    item_code        VARCHAR(30) NOT NULL REFERENCES item(item_code),
    origin_region_id SMALLINT    NOT NULL DEFAULT 0,   -- 0 = 수입(시·도 없음)
    is_import        BOOLEAN     NOT NULL,
    volume_kg        NUMERIC,
    amount_won       NUMERIC,
    price            INT,
    PRIMARY KEY (date, market_code, item_code, origin_region_id, is_import)
);

CREATE TABLE IF NOT EXISTS price_unit_daily (
    date       DATE  NOT NULL,
    unit_id    INT   NOT NULL REFERENCES variety_unit(unit_id),
    volume_kg  NUMERIC,
    amount_won NUMERIC,
    price      INT,
    PRIMARY KEY (date, unit_id)
);

CREATE TABLE IF NOT EXISTS retail_price_daily (
    date        DATE        NOT NULL,
    item_code   VARCHAR(30) NOT NULL REFERENCES item(item_code),
    price       INT,
    source_spec VARCHAR(80),
    PRIMARY KEY (date, item_code)
);

-- 연 생산 통계 (11-11): 원인 모델(S0)의 탄력·평균 변화·되돌림 재료. 공급 단위 = 품목 또는 품목_작형(배추_가을 등)·만감 품종
-- price_year 는 연 평균 가격(원/kg) — 계수(탄력 e·평균 변화 a)를 배울 때만 쓰고 예측 입력에는 넣지 않음 (강사님 원칙)
-- 출처: KOSIS 재배면적·생산량, 43번 시설채소 생산실적, 만감 품종 통계 등을 원인 모델 34·35번에서 공급 단위로 정리한 연 표를 내보낸 것 (11-11). 해마다 통계가 나오면 한 줄씩 더함
CREATE TABLE IF NOT EXISTS production_yearly (
    supply_unit  VARCHAR(30) NOT NULL,
    year         SMALLINT    NOT NULL,             -- 수확 해
    production_t DOUBLE PRECISION,                 -- 생산량(t)
    area_ha      DOUBLE PRECISION,                 -- 재배면적(ha)
    price_year   DOUBLE PRECISION,                 -- 연 평균 가격(원/kg), 계수 추정용 (계수가 그대로 나오게 반올림 안 함)
    source       VARCHAR(20),
    PRIMARY KEY (supply_unit, year)
);

-- 가격 예측 (11-11): 기준월에 만든 1~12달 뒤 월 예측. 전국 도매 단가(원/kg). variety_id 'ALL' = 품목 전체, 그 밖 = shared/items50.json 품종 id
-- 시장별 값은 ml-api 가 market_factor 를 곱함. 만드는 법: tools/build_v4_forecast.py (팀 v4 상황판 예측)
CREATE TABLE IF NOT EXISTS price_forecast_monthly (
    base_month   DATE        NOT NULL,
    item_code    VARCHAR(30) NOT NULL REFERENCES item(item_code),
    variety_id   VARCHAR(40) NOT NULL DEFAULT 'ALL',
    target_month DATE        NOT NULL,
    price        INT         NOT NULL,
    price_low    INT,
    price_high   INT,
    model        VARCHAR(40),
    method       VARCHAR(120),
    PRIMARY KEY (base_month, item_code, variety_id, target_month)
);

-- 가격 예측 일 단위 (11-12): 기준일에 만든 1~365일 뒤 하루 값. 전국 도매 단가(원/kg). variety_id 'ALL' = 품목 전체, 그 밖 = shared/items50.json 품종 id
-- 만드는 법: python-ml/3_forecast.py (팀원 u7c·v4 + 원인 모델 섞기). 시장별 값은 ml-api 가 market_factor 를 곱함. 예측 없는 날(출하철 밖)은 줄 없음
CREATE TABLE IF NOT EXISTS price_forecast_daily (
    base_date    DATE        NOT NULL,
    item_code    VARCHAR(30) NOT NULL REFERENCES item(item_code),
    variety_id   VARCHAR(40) NOT NULL DEFAULT 'ALL',
    target_date  DATE        NOT NULL,
    price        INT         NOT NULL,
    price_low    INT,
    price_high   INT,
    model        VARCHAR(60),
    off_season   SMALLINT    NOT NULL DEFAULT 0,  -- 1 = 출하철 밖 날 (두 모델 다 채점해 본 적 없는 달 → 화면 '참고', 11-13)
    PRIMARY KEY (base_date, item_code, variety_id, target_date)
);
-- 11-13 전에 만든 DB 에도 열 추가 (이미 있으면 그대로)
ALTER TABLE price_forecast_daily ADD COLUMN IF NOT EXISTS off_season SMALLINT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS price_index_daily (
    date       DATE         NOT NULL,
    group_code VARCHAR(20)  NOT NULL,
    value      NUMERIC(7,2),
    item_count SMALLINT,
    PRIMARY KEY (date, group_code)
);

-- 점검에서 더한 표: 시장별 예측 = 전국 예측 × factor
CREATE TABLE IF NOT EXISTS market_factor (
    item_code   VARCHAR(30) NOT NULL REFERENCES item(item_code),
    market_code VARCHAR(10) NOT NULL REFERENCES market(market_code),
    month       SMALLINT    NOT NULL,
    factor      NUMERIC(6,4),
    days        INT,
    period      VARCHAR(20),
    PRIMARY KEY (item_code, market_code, month)
);

CREATE TABLE IF NOT EXISTS weather_daily (
    date      DATE     NOT NULL,
    region_id SMALLINT NOT NULL REFERENCES region(region_id),
    temp_avg  NUMERIC(4,1), temp_min NUMERIC(4,1), temp_max NUMERIC(4,1),
    rain_mm   NUMERIC(6,1), sun_hr NUMERIC(4,1), humidity NUMERIC(4,1),
    wind      NUMERIC(4,1),                     -- 최대풍속 m/s (AWS 일통계에 평균풍속이 없어 최대풍속)
    PRIMARY KEY (date, region_id)
);

-- 점검에서 더한 표: 홈 '최근 7일 평년 대비' (1991~2020 같은 날짜 앞뒤 3일 평균)
CREATE TABLE IF NOT EXISTS weather_normal (
    region_id   SMALLINT NOT NULL REFERENCES region(region_id),
    month       SMALLINT NOT NULL,
    day         SMALLINT NOT NULL,
    temp_normal     NUMERIC(5,2),
    temp_max_normal NUMERIC(5,2),
    temp_min_normal NUMERIC(5,2),
    rain_normal     NUMERIC(6,2),
    PRIMARY KEY (region_id, month, day)
);

CREATE TABLE IF NOT EXISTS weather_region_now (
    base_time  TIMESTAMPTZ NOT NULL,
    region_id  SMALLINT    NOT NULL REFERENCES region(region_id),
    temp NUMERIC(4,1), temp_min NUMERIC(4,1), temp_max NUMERIC(4,1),
    sky VARCHAR(10), icon VARCHAR(10), rain_prob SMALLINT, humidity SMALLINT, wind NUMERIC(4,1),
    soil_temp NUMERIC(4,1), note VARCHAR(100),
    PRIMARY KEY (base_time, region_id)
);

CREATE TABLE IF NOT EXISTS weather_warning_daily (
    date       DATE        NOT NULL,
    region_id  SMALLINT    NOT NULL REFERENCES region(region_id),
    warn_type  VARCHAR(10) NOT NULL,            -- 호우 폭염 한파 대설 태풍 강풍 건조 황사
    level      SMALLINT,                        -- 1 주의보 · 2 경보 · 3 중대경보
    area_share NUMERIC(4,3),                    -- 그날 특보가 걸린 육상 구역 비중
    PRIMARY KEY (date, region_id, warn_type)
);

-- ── 예측 입력·화면 보조 (설계안 밖, 2026-11-06 더함) ──
-- 산지공판장 목록 (11-12): 공판장 코드 → 이름 · 시·도. 시세 화면 '산지공판장 가격' 카드의 시·도 칸. 만드는 법: tools/import_producer_csv.py (팀 107번 위치 추정)
CREATE TABLE IF NOT EXISTS producer (
    producer_code  VARCHAR(12) PRIMARY KEY,
    producer_name  VARCHAR(40),
    sido           VARCHAR(10),                      -- 출하 물량 1위 시·도 (공판장 위치 추정)
    sigungu        VARCHAR(20),
    sido_share_pct NUMERIC                           -- 그 시·도 물량 몫(%)
);

CREATE TABLE IF NOT EXISTS producer_price_daily (     -- 산지공판장
    date          DATE        NOT NULL,
    producer_code VARCHAR(12) NOT NULL,              -- 공판장 코드, 전국 = 'national'
    producer_name VARCHAR(40),
    item_code     VARCHAR(30) NOT NULL REFERENCES item(item_code),
    volume_kg NUMERIC, amount_won NUMERIC, price INT,
    PRIMARY KEY (date, producer_code, item_code)
);

-- 시장 × 품종 단위 × 달 (11-12): 시세 화면 '도매시장별 가격' 카드에서 품종을 골랐을 때 (최근 12달 시장별 평균 경락가 · 물량 몫).
-- 품목 전체는 price_daily(시장 × 품목, grade='ALL') 로 충분. 계산은 price_unit_daily 와 같고 시장별·달별로만 묶음 (시장 합 = 전국 단위 값)
-- 만드는 법: tools/build_unit_market_monthly.py
CREATE TABLE IF NOT EXISTS price_unit_market_monthly (
    month       DATE        NOT NULL,                -- 그 달 1일
    market_code VARCHAR(10) NOT NULL,
    unit_id     INT         NOT NULL,
    volume_kg   NUMERIC,
    amount_won  NUMERIC,
    price       INT,                                 -- 금액 ÷ 물량 (원/kg)
    days        INT,                                 -- 그 달 거래일 수
    PRIMARY KEY (month, market_code, unit_id)
);

CREATE TABLE IF NOT EXISTS garak_inout_daily (        -- 가락 경매전(그날 경매 전 집계)·경매후(그날 실제 반입)
    date        DATE        NOT NULL,
    kind        VARCHAR(6)  NOT NULL,                -- before / after
    garak_name  VARCHAR(40) NOT NULL,
    garak_code  VARCHAR(10) NOT NULL DEFAULT '-',    -- 경매전 자료는 코드가 없어 '-'
    item_code   VARCHAR(30) NOT NULL DEFAULT '-',    -- 50품목에 없으면 '-'
    volume_kg   NUMERIC,
    PRIMARY KEY (date, kind, garak_name, garak_code, item_code)
);

CREATE TABLE IF NOT EXISTS shipment_reservation_daily (   -- aT 전국 도매시장 출하예약(전자송품장)
    date          DATE        NOT NULL,               -- 출하예정일
    market_code   VARCHAR(10) NOT NULL,
    item_code     VARCHAR(30) NOT NULL REFERENCES item(item_code),
    variety_code  VARCHAR(4)  NOT NULL,               -- 공영 소분류(품종)코드
    reserved_kg   NUMERIC,
    invoice_rows  INT,
    collected_at  TIMESTAMPTZ,                        -- 이 값을 받은 시각 (예정일 전에 알 수 있었던 양 판단용)
    PRIMARY KEY (date, market_code, item_code, variety_code)
);

CREATE TABLE IF NOT EXISTS fx_daily (
    date          DATE        NOT NULL,
    currency_code VARCHAR(10) NOT NULL,
    currency_name VARCHAR(40),
    rate          NUMERIC(10,2),
    PRIMARY KEY (date, currency_code)
);

CREATE TABLE IF NOT EXISTS policy_doc (                -- 정부 수급정책 보도자료·공고 (공지 후보, 정부 개입 시점)
    doc_id  VARCHAR(20) PRIMARY KEY,
    date    DATE,
    source  VARCHAR(30),
    title   VARCHAR(300),
    url     VARCHAR(500),
    status  VARCHAR(20),
    collected_at TIMESTAMPTZ                          -- date 가 비면 이 시각 전에 공개된 문서
);

CREATE TABLE IF NOT EXISTS collect_log (
    log_id        BIGSERIAL   PRIMARY KEY,
    source        VARCHAR(20),
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    ok            BOOLEAN,
    rows_in       INT, rows_saved INT, rows_rejected INT, api_calls INT,
    error         TEXT,
    note          TEXT,
    UNIQUE (source, started_at)
);
