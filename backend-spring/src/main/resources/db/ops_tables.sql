-- 관리자 운영 표 (11-17). 서버(Spring)가 켜질 때마다 실행 — 이미 있으면 그대로.
-- 사이트 설정: 공지 띠 · 점검 안내 · 팀 소개 · 연락처 · 게시판 금칙어 (관리자 사이트 '사이트 설정'에서 고침, 코드 수정·재배포 없이)
CREATE TABLE IF NOT EXISTS site_setting (
    key         VARCHAR(40)  PRIMARY KEY,
    value       TEXT         NOT NULL DEFAULT '',
    updated_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

-- 관리자가 숨긴 뉴스 기사 (수집 파일은 그대로 두고 화면에서만 뺌). url = 기사 주소
CREATE TABLE IF NOT EXISTS news_hidden (
    url         VARCHAR(600) PRIMARY KEY,
    title       VARCHAR(300),
    reason      VARCHAR(200),
    admin_id    BIGINT       REFERENCES admin(admin_id) ON DELETE SET NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);
