package com.farm.backend.controller;

import com.farm.backend.config.AdminUser;
import com.farm.backend.config.ApiException;
import com.farm.backend.service.SiteSettings;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 사이트 설정 · 숨긴 뉴스 (11-17)
 *   GET  /api/site                  누구나: 공지 띠 · 점검 안내 · 팀 소개 · 연락처 (금칙어는 안 나감)
 *   GET  /api/news/hidden           누구나: 숨긴 기사 주소 목록 (화면이 수집 파일에서 이 기사만 뺌)
 *   GET  /api/admin/site            관리자: 모든 설정 (금칙어 포함)
 *   PUT  /api/admin/site            관리자: 설정 고치기 {키: 값}
 *   GET  /api/admin/news/hidden     관리자: 숨긴 기사 (제목 · 사유 · 시각)
 *   POST /api/admin/news/hidden     관리자: 기사 숨기기 {url, title, reason}
 *   DELETE /api/admin/news/hidden?url=   관리자: 다시 보이기
 * /api/admin/** 는 SecurityConfig 가 관리자 로그인만 통과시킴
 */
@RestController
@RequestMapping("/api")
public class SiteController {
    private final SiteSettings settings;
    private final NamedParameterJdbcTemplate jdbc;

    public SiteController(SiteSettings settings, NamedParameterJdbcTemplate jdbc) {
        this.settings = settings;
        this.jdbc = jdbc;
    }

    @GetMapping("/site")
    public Map<String, Object> site() {
        return settings.publicView();
    }

    @GetMapping("/admin/site")
    public Map<String, String> adminSite() {
        return settings.all();
    }

    @PutMapping("/admin/site")
    public Map<String, String> save(@RequestBody Map<String, String> patch) {
        return settings.save(patch);
    }

    @GetMapping("/news/hidden")
    public List<String> hiddenUrls() {
        return jdbc.queryForList("SELECT url FROM news_hidden ORDER BY created_at DESC LIMIT 2000", new MapSqlParameterSource(), String.class);
    }

    @GetMapping("/admin/news/hidden")
    public List<Map<String, Object>> hidden() {
        return jdbc.query("SELECT url, title, reason, created_at FROM news_hidden ORDER BY created_at DESC LIMIT 2000", new MapSqlParameterSource(),
                (rs, i) -> {
                    Map<String, Object> m = new HashMap<>();
                    m.put("url", rs.getString("url"));
                    m.put("title", rs.getString("title"));
                    m.put("reason", rs.getString("reason"));
                    m.put("created_at", rs.getTimestamp("created_at").toLocalDateTime().toString());
                    return m;
                });
    }

    public record HideRequest(String url, String title, String reason) {
    }

    @PostMapping("/admin/news/hidden")
    public ResponseEntity<Void> hide(@AuthenticationPrincipal AdminUser admin, @RequestBody HideRequest r) {
        String url = r.url() == null ? "" : r.url().trim();
        if (!url.matches("^https?://\\S{4,590}$")) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "기사 주소를 확인하세요");
        MapSqlParameterSource p = new MapSqlParameterSource().addValue("u", url).addValue("t", cut(r.title(), 300)).addValue("r", cut(r.reason(), 200))
                .addValue("a", admin == null ? null : admin.id());
        jdbc.update("INSERT INTO news_hidden (url, title, reason, admin_id) VALUES (:u, :t, :r, :a) "
                + "ON CONFLICT (url) DO UPDATE SET reason = EXCLUDED.reason, created_at = NOW()", p);
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/admin/news/hidden")
    public ResponseEntity<Void> unhide(@RequestParam String url) {
        jdbc.update("DELETE FROM news_hidden WHERE url = :u", Map.of("u", url.trim()));
        return ResponseEntity.noContent().build();
    }

    private static String cut(String s, int max) {
        if (s == null) return null;
        String t = s.trim();
        return t.isEmpty() ? null : t.length() > max ? t.substring(0, max) : t;
    }
}
