package com.farm.backend.controller;

import com.farm.backend.service.UserService;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.sql.Timestamp;
import java.util.List;
import java.util.Map;

/**
 * 관리자 회원 관리 (11-17) — 관리자 로그인(ROLE_ADMIN)만 (SecurityConfig /api/admin/**). 보기만 함 (정지 기능 없음, 탈퇴는 회원 본인만)
 *   GET /api/admin/users   회원 목록 (최근 가입 순): id · email · nickname · region · farm_name · joined · posts · comments
 *   GET /api/admin/stats   대시보드 숫자: members · joined_today · joined_7d
 * 비밀번호 해시·전화번호는 내보내지 않음
 */
@RestController
@RequestMapping("/api/admin")
public class AdminUserController {
    private static final String USERS_SQL = """
            SELECT u.user_id, u.email, u.name, u.region_id, u.farm_name, u.created_at,
                   (SELECT count(*) FROM post p WHERE p.author_id = u.user_id) AS posts,
                   (SELECT count(*) FROM post_comment c WHERE c.author_id = u.user_id) AS comments
            FROM users u ORDER BY u.created_at DESC, u.user_id DESC""";
    private static final String STATS_SQL = """
            SELECT count(*) AS members,
                   count(*) FILTER (WHERE created_at >= current_date) AS joined_today,
                   count(*) FILTER (WHERE created_at >= current_date - 6) AS joined_7d
            FROM users""";

    private final NamedParameterJdbcTemplate jdbc;

    public AdminUserController(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public record MemberRow(long id, String email, String nickname, String region, String farmName, String joined, long posts, long comments) {
    }

    @GetMapping("/users")
    public List<MemberRow> users() {
        return jdbc.query(USERS_SQL, new MapSqlParameterSource(), (rs, i) -> {
            Timestamp t = rs.getTimestamp("created_at");
            int region = rs.getInt("region_id");
            String regionName = rs.wasNull() ? null : UserService.regionName(region);
            return new MemberRow(rs.getLong("user_id"), rs.getString("email"), rs.getString("name"),
                    regionName, rs.getString("farm_name"),
                    t == null ? null : t.toLocalDateTime().toLocalDate().toString(), rs.getLong("posts"), rs.getLong("comments"));
        });
    }

    @GetMapping("/stats")
    public Map<String, Long> stats() {
        return jdbc.queryForObject(STATS_SQL, new MapSqlParameterSource(), (rs, i) -> Map.of(
                "members", rs.getLong("members"), "joined_today", rs.getLong("joined_today"), "joined_7d", rs.getLong("joined_7d")));
    }
}
