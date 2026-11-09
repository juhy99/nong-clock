-- 수집·시세·날씨 표 (팀 수집기 farmbid_daily/schema.sql 과 같은 내용, 2026-11-09 복사).
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
CREATE TABLE IF NOT EXISTS producer_price_daily (     -- 산지공판장
    date          DATE        NOT NULL,
    producer_code VARCHAR(12) NOT NULL,              -- 공판장 코드, 전국 = 'national'
    producer_name VARCHAR(40),
    item_code     VARCHAR(30) NOT NULL REFERENCES item(item_code),
    volume_kg NUMERIC, amount_won NUMERIC, price INT,
    PRIMARY KEY (date, producer_code, item_code)
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
