-- 댓글 표 (11-10). 서버(Spring)가 켜질 때마다 실행되지만 IF NOT EXISTS 라 이미 있으면 아무것도 안 함.
-- 이미 만들어 둔 DB(도커 볼륨)에도 자동으로 생기게 하려고 db/init/farm_table.sql 과 별도로 둠 (application.yml spring.sql.init)
-- 글이 지워지면 그 글의 댓글도, 댓글이 지워지면 그 답글도 DB 가 같이 지움 (ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS post_comment (
    comment_id  BIGSERIAL  PRIMARY KEY,
    post_id     BIGINT     NOT NULL REFERENCES post(post_id) ON DELETE CASCADE,
    parent_id   BIGINT     REFERENCES post_comment(comment_id) ON DELETE CASCADE,
    author_id   BIGINT     NOT NULL REFERENCES users(user_id),
    body        TEXT       NOT NULL,
    deleted     BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_post_comment_post ON post_comment (post_id, created_at);
CREATE INDEX IF NOT EXISTS idx_post_comment_author ON post_comment (author_id);
