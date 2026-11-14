-- 회원·게시글 표 (11-14). 서버(Spring)가 켜질 때마다 실행되지만 IF NOT EXISTS 라 이미 있으면 아무것도 안 함.
-- 예전에 만든 DB(도커 볼륨)에 이 표가 없으면 직접 SQL 을 돌리지 않아도 생기게 (db/init/farm_table.sql 과 내용 같음)
CREATE TABLE IF NOT EXISTS users (
    user_id          BIGSERIAL     PRIMARY KEY,
    email            VARCHAR(100)  NOT NULL UNIQUE,
    password_hash    VARCHAR(100)  NOT NULL,
    name             VARCHAR(30)   NOT NULL,
    phone            VARCHAR(20)   NOT NULL,
    region_id        INT,
    farm_name        VARCHAR(50),
    marketing_agree  BOOLEAN       NOT NULL DEFAULT FALSE,
    status           VARCHAR(20)   NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED','WITHDRAWN')),
    role             VARCHAR(10)   NOT NULL DEFAULT 'MEMBER' CHECK (role IN ('MEMBER','ADMIN')),
    notify_settings  JSONB         NOT NULL DEFAULT '{}',
    board_banned_at  TIMESTAMP,
    board_ban_until  TIMESTAMP,
    board_ban_reason VARCHAR(200),
    board_ban_by     INT,
    created_at       TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- 회원 구분 열 (11-14): 이미 있던 users 표에도 더함. 관리자는 서버 .env 의 ADMIN_EMAILS 로 지정 (config/AdminAccounts.java)
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(10) NOT NULL DEFAULT 'MEMBER' CHECK (role IN ('MEMBER','ADMIN'));

CREATE TABLE IF NOT EXISTS post (
    post_id        BIGSERIAL     PRIMARY KEY,
    author_id      BIGINT        NOT NULL REFERENCES users(user_id),
    category       VARCHAR(20)   NOT NULL CHECK (category IN ('FREE','QUESTION','INFO','REVIEW')),
    title          VARCHAR(80)   NOT NULL,
    body           TEXT          NOT NULL,
    views          INT           NOT NULL DEFAULT 0,
    status         VARCHAR(20)   NOT NULL DEFAULT 'VISIBLE' CHECK (status IN ('VISIBLE','HIDDEN','DELETED')),
    hidden_reason  VARCHAR(200),
    hidden_by      INT,
    created_at     TIMESTAMP     NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_post_list ON post (status, category, created_at DESC);
