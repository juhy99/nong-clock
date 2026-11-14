-- 관리자 (11-14). 서버(Spring)가 켜질 때마다 실행 — 이미 있으면 그대로 (IF NOT EXISTS · 같은 제약을 지우고 다시 만듦).
-- 관리자 계정은 일반 회원(users)과 따로. 관리자 사이트(/admin/)는 이 표로만 로그인한다. 계정 넣는 SQL 은 deploy/README.md 1-2
CREATE TABLE IF NOT EXISTS admin (
    admin_id       BIGSERIAL     PRIMARY KEY,
    email          VARCHAR(100)  NOT NULL UNIQUE,   -- 로그인 아이디 (소문자로 넣을 것)
    password_hash  VARCHAR(100)  NOT NULL,          -- BCrypt ($2a$…). SQL: crypt('비밀번호', gen_salt('bf', 10)) (pgcrypto)
    name           VARCHAR(30)   NOT NULL,          -- 관리자 사이트 위에 보이는 이름
    created_at     TIMESTAMP     NOT NULL DEFAULT NOW()
);

-- 관리자가 쓴 글·댓글: author_id(회원) 대신 admin_id. 둘 중 하나만 있음
ALTER TABLE post ALTER COLUMN author_id DROP NOT NULL;
ALTER TABLE post ADD COLUMN IF NOT EXISTS admin_id BIGINT REFERENCES admin(admin_id) ON DELETE SET NULL;
-- 말머리에 공지(NOTICE) 추가 — 관리자만 씀, 게시판 맨 위에 보임
ALTER TABLE post DROP CONSTRAINT IF EXISTS post_category_check;
ALTER TABLE post ADD CONSTRAINT post_category_check CHECK (category IN ('FREE','QUESTION','INFO','REVIEW','NOTICE'));
ALTER TABLE post_comment ALTER COLUMN author_id DROP NOT NULL;
ALTER TABLE post_comment ADD COLUMN IF NOT EXISTS admin_id BIGINT REFERENCES admin(admin_id) ON DELETE SET NULL;
