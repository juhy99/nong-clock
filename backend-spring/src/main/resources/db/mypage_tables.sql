-- 마이페이지 (11-16). 서버(Spring)가 켜질 때마다 실행 — 이미 있으면 그대로 (IF NOT EXISTS)
-- 관심 품목: 회원 × 품목 코드(예측 50품목, item 표). 회원이 탈퇴하면 같이 지워짐 (ON DELETE CASCADE)
CREATE TABLE IF NOT EXISTS user_favorite (
    user_id     BIGINT       NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    item_code   VARCHAR(30)  NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, item_code)
);
