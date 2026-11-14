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

-- 1-2. 관리자 (11-14): 일반 회원과 따로. 관리자 사이트(/admin/)는 이 표로만 로그인. 계정은 SQL 로 직접 넣음 (deploy/README.md 1-2)
CREATE TABLE admin (
    admin_id       BIGSERIAL     PRIMARY KEY,
    email          VARCHAR(100)  NOT NULL UNIQUE,
    password_hash  VARCHAR(100)  NOT NULL,
    name           VARCHAR(30)   NOT NULL,
    created_at     TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- 2. 게시글 테이블 생성 (users 생성 후 생성). 회원 글은 author_id, 관리자 글(공지 등)은 admin_id (11-14)
CREATE TABLE post (
    post_id        BIGSERIAL     PRIMARY KEY,
    author_id      BIGINT        REFERENCES users(user_id),
    admin_id       BIGINT        REFERENCES admin(admin_id) ON DELETE SET NULL,
    category       VARCHAR(20)   NOT NULL CHECK (category IN ('FREE','QUESTION','INFO','REVIEW','NOTICE')),
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

-- 3. 댓글 테이블 (11-10). 이미 만든 DB 에는 Spring 이 켜질 때 backend-spring/src/main/resources/db/post_comment.sql 로 만든다 (내용 같음)
-- 글이 지워지면 그 글의 댓글도, 댓글이 지워지면 그 답글도 같이 지워짐 (ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS post_comment (
    comment_id  BIGSERIAL  PRIMARY KEY,
    post_id     BIGINT     NOT NULL REFERENCES post(post_id) ON DELETE CASCADE,
    parent_id   BIGINT     REFERENCES post_comment(comment_id) ON DELETE CASCADE,
    author_id   BIGINT     REFERENCES users(user_id),
    admin_id    BIGINT     REFERENCES admin(admin_id) ON DELETE SET NULL,  -- 관리자 댓글 (11-14)
    body        TEXT       NOT NULL,
    deleted     BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_post_comment_post ON post_comment (post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_post_comment_author ON post_comment (author_id);