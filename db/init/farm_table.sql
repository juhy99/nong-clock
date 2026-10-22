-- 1. 회원 테이블 생성 (먼저 생성)
CREATE TABLE users (
    user_id          BIGSERIAL     PRIMARY KEY,
    email            VARCHAR(100)  NOT NULL UNIQUE,
    password_hash    VARCHAR(100)  NOT NULL,
    name             VARCHAR(30)   NOT NULL,
    phone            VARCHAR(20)   NOT NULL,
    region_id        INT,
    farm_name        VARCHAR(50),
    marketing_agree  BOOLEAN       NOT NULL DEFAULT FALSE,
    status           VARCHAR(20)   NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED','WITHDRAWN')),
    notify_settings  JSONB         NOT NULL DEFAULT '{}',
    board_banned_at  TIMESTAMP,
    board_ban_until  TIMESTAMP,
    board_ban_reason VARCHAR(200),
    board_ban_by     INT,
    created_at       TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- 2. 게시글 테이블 생성 (users 생성 후 생성)
CREATE TABLE post (
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
CREATE INDEX idx_post_list ON post (status, category, created_at DESC);