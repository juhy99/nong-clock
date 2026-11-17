package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;

/**
 * 사이트 설정 (11-17, DB 표 site_setting) — 관리자 사이트에서 고치고 사용자 사이트가 읽음.
 * 공지 띠 · 점검 안내 · 팀 소개("이름 | 역할" 한 줄씩) · 연락처 · 게시판 금칙어(바깥에는 안 내보냄).
 * 읽기는 15초 기억 (화면마다 부르므로), 고치면 바로 비움.
 */
@Service
public class SiteSettings {
    /** 고칠 수 있는 키와 최대 글자 수 — 이 밖의 키는 거부 */
    static final Map<String, Integer> KEYS = Map.of(
            "notice_on", 5, "notice_text", 200, "maintenance_on", 5, "maintenance_text", 200,
            "team_text", 1000, "contact_email", 100, "contact_phone", 30, "contact_hours", 60, "banned_words", 2000);
    private static final long TTL_MS = 15_000;

    private final NamedParameterJdbcTemplate jdbc;
    private volatile Map<String, String> cache;
    private volatile long cachedAt;

    public SiteSettings(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 모든 설정 (없는 키는 빈 글자) */
    public Map<String, String> all() {
        Map<String, String> c = cache;
        if (c != null && System.currentTimeMillis() - cachedAt < TTL_MS) return c;
        Map<String, String> m = new TreeMap<>();
        KEYS.keySet().forEach(k -> m.put(k, ""));
        jdbc.query("SELECT key, value FROM site_setting", new MapSqlParameterSource(), rs -> {
            if (KEYS.containsKey(rs.getString("key"))) m.put(rs.getString("key"), rs.getString("value"));
        });
        cache = Collections.unmodifiableMap(m);
        cachedAt = System.currentTimeMillis();
        return cache;
    }

    @Transactional
    public Map<String, String> save(Map<String, String> patch) {
        if (patch == null || patch.isEmpty()) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "바꿀 설정이 없습니다");
        for (Map.Entry<String, String> e : patch.entrySet()) {
            Integer max = KEYS.get(e.getKey());
            if (max == null) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "모르는 설정입니다: " + e.getKey());
            String v = e.getValue() == null ? "" : e.getValue().trim();
            if (v.length() > max) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, label(e.getKey()) + "은(는) " + max + "자까지 넣을 수 있어요");
            if (e.getKey().endsWith("_on") && !v.isEmpty() && !v.equals("true") && !v.equals("false"))
                throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "켜기·끄기 값은 true 또는 false");
            if (e.getKey().equals("contact_email") && !v.isEmpty() && !v.matches("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$"))
                throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "연락처 이메일 형식을 확인하세요");
            jdbc.update("INSERT INTO site_setting (key, value, updated_at) VALUES (:k, :v, NOW()) "
                    + "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()", Map.of("k", e.getKey(), "v", v));
        }
        cache = null;
        return all();
    }

    static String label(String key) {
        return switch (key) {
            case "notice_text" -> "공지 문장";
            case "maintenance_text" -> "점검 안내 문장";
            case "team_text" -> "팀 소개";
            case "banned_words" -> "금칙어 목록";
            default -> key;
        };
    }

    /** 사용자 사이트에 내보내는 모양 (금칙어는 빼고) */
    public Map<String, Object> publicView() {
        Map<String, String> s = all();
        List<Map<String, String>> team = new ArrayList<>();
        for (String line : s.get("team_text").split("\\R")) {
            String[] p = line.split("\\|", 2);
            if (p[0].isBlank()) continue;
            team.add(Map.of("name", p[0].trim(), "role", p.length > 1 ? p[1].trim() : ""));
            if (team.size() >= 12) break;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("notice", "true".equals(s.get("notice_on")) ? s.get("notice_text") : "");
        out.put("maintenance", "true".equals(s.get("maintenance_on")) ? s.get("maintenance_text") : "");
        out.put("team", team);
        out.put("contact", Map.of("email", s.get("contact_email"), "phone", s.get("contact_phone"), "hours", s.get("contact_hours")));
        return out;
    }

    /** 금칙어 (쉼표·줄바꿈으로 나눔, 소문자) */
    public List<String> bannedWords() {
        List<String> out = new ArrayList<>();
        for (String w : all().get("banned_words").split("[,\\r\\n]+")) {
            String t = w.trim().toLowerCase(Locale.ROOT);
            if (t.length() >= 2) out.add(t);   // 한 글자 금칙어는 너무 많은 글이 걸려서 무시
        }
        return out;
    }

    /** 글·댓글에 금칙어가 있으면 422 (회원이 쓸 때만 부름 — 관리자 글은 검사 안 함). 띄어쓰기를 빼고도 찾음 */
    public void checkWords(String... texts) {
        List<String> banned = bannedWords();
        if (banned.isEmpty()) return;
        StringBuilder sb = new StringBuilder();
        for (String t : texts) if (t != null) sb.append(t).append('\n');
        String raw = sb.toString().toLowerCase(Locale.ROOT), tight = raw.replaceAll("\\s+", "");
        for (String w : banned)
            if (raw.contains(w) || tight.contains(w.replaceAll("\\s+", "")))
                throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "게시판에 쓸 수 없는 낱말이 들어 있어요. 내용을 고쳐 주세요");
    }
}
