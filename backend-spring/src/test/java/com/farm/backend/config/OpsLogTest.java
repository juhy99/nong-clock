package com.farm.backend.config;

import org.junit.jupiter.api.Test;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/** 11-17 오류 기록: 문제 응답만 · IP 끝자리 가림 · 최근 300건 · 48시간 시간대별 횟수 */
class OpsLogTest {
    private LocalDateTime now = LocalDateTime.of(2026, 11, 17, 10, 30);
    private final OpsLog log = new OpsLog(() -> now);

    @SuppressWarnings("unchecked")
    @Test
    void records_only_problems_and_masks_ip() {
        log.record(200, "GET", "/api/posts", "10.0.0.7", null);
        log.record(401, "GET", "/api/me", "10.0.0.7", null);                 // 로그인 안 한 요청은 문제가 아님
        log.record(401, "POST", "/api/auth/login", "10.0.0.7", null);        // 로그인 실패
        log.record(429, "POST", "/api/posts", "10.0.0.7", null);
        log.record(500, "PUT", "/api/me/favorites", "10.0.0.7", "BadSqlGrammarException");
        Map<String, Object> s = log.snapshot();
        List<OpsLog.Event> ev = (List<OpsLog.Event>) s.get("events");
        assertThat(ev).extracting(OpsLog.Event::kind).containsExactly("server", "limit", "login");   // 최근 것부터
        assertThat(ev.get(0).ip()).isEqualTo("10.0.0.*");
        assertThat(ev.get(0).note()).isEqualTo("BadSqlGrammarException");
        assertThat(s.get("total")).isEqualTo(Map.of("server", 1, "limit", 1, "login", 1));
        assertThat((List<Map<String, Object>>) s.get("hours")).singleElement().satisfies(h -> assertThat(h.get("hour")).isEqualTo("2026-11-17T10"));
    }

    @SuppressWarnings("unchecked")
    @Test
    void keeps_last_300_and_drops_hours_older_than_48h() {
        for (int i = 0; i < 320; i++) log.record(500, "GET", "/api/x" + i, "1.2.3.4", null);
        now = now.plusHours(49);
        log.record(429, "POST", "/api/posts", "1.2.3.4", null);
        Map<String, Object> s = log.snapshot();
        assertThat((List<OpsLog.Event>) s.get("events")).hasSize(300);
        assertThat((List<Map<String, Object>>) s.get("hours")).singleElement().satisfies(h -> assertThat(h.get("limit")).isEqualTo(1));
    }
}
