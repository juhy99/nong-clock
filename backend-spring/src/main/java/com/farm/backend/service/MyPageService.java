package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.User;
import com.farm.backend.dto.MyCommentResponse;
import com.farm.backend.dto.PasswordRequest;
import com.farm.backend.dto.PostResponse;
import com.farm.backend.dto.ProfileRequest;
import com.farm.backend.repository.UserRepository;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 마이페이지 (11-16) — 명세서 2-6 ~ 2-8
 *   내 정보 수정(닉네임·연락처·지역·농장명, 이메일은 못 바꿈) · 비밀번호 변경 · 내가 쓴 글·댓글 · 관심 품목(user_favorite 표)
 * 모든 기능은 로그인한 회원 자신의 것만 (회원 번호는 세션에서, 요청 본문의 id 는 받지 않음)
 */
@Service
@Transactional(readOnly = true)
public class MyPageService {
    static final int MAX_FAVORITES = 50;   // 예측 품목 수
    static final int MY_LIST_MAX = 100;    // 내가 쓴 글·댓글을 한 번에 보여 주는 최대 줄 수

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final NamedParameterJdbcTemplate jdbc;

    public MyPageService(UserRepository userRepository, PasswordEncoder passwordEncoder, NamedParameterJdbcTemplate jdbc) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jdbc = jdbc;
    }

    private User user(Long id) {
        return userRepository.findById(id).orElseThrow(() -> new ApiException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다"));
    }

    /** PATCH /api/me — 닉네임은 다른 회원과 겹치면 409 (자기 닉네임 그대로는 괜찮음) */
    @Transactional
    public User updateProfile(Long id, ProfileRequest r) {
        User u = user(id);
        // 11-17: 닉네임을 그대로 두면 새 규칙 검사를 건너뜀 (규칙 전에 가입한 회원이 다른 정보만 고칠 수 있게)
        String raw = r.nickname() != null && !r.nickname().isBlank() ? r.nickname() : r.name();
        String nickname = raw != null && raw.trim().equals(u.getName()) ? u.getName() : UserService.normNickname(r.nickname(), r.name());
        if (!nickname.equalsIgnoreCase(u.getName()) && userRepository.existsByNameIgnoreCase(nickname))
            throw new ApiException(HttpStatus.CONFLICT, "이미 사용 중인 닉네임이에요");
        Integer region = UserService.regionId(r.region());
        if (region == null) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "지역을 선택하세요");
        u.setName(nickname);
        u.setPhone(r.phone().trim());
        u.setRegionId(region);
        u.setFarmName(r.farmName() == null || r.farmName().isBlank() ? null : r.farmName().trim());
        try {
            return userRepository.saveAndFlush(u);
        } catch (DataIntegrityViolationException e) {
            throw new ApiException(HttpStatus.CONFLICT, "이미 사용 중인 닉네임이에요");
        }
    }

    /** PUT /api/me/password — 지금 비밀번호가 틀리면 403, 새 비밀번호가 지금과 같으면 422 */
    @Transactional
    public void changePassword(Long id, PasswordRequest r) {
        User u = user(id);
        if (!passwordEncoder.matches(r.current(), u.getPasswordHash()))
            throw new ApiException(HttpStatus.FORBIDDEN, "지금 비밀번호가 맞지 않습니다");
        if (r.current().equals(r.next()))
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "새 비밀번호가 지금 비밀번호와 같아요");
        u.setPasswordHash(passwordEncoder.encode(r.next()));
        userRepository.save(u);
    }

    /** GET /api/me/posts — 내가 쓴 글 (최근 순, 관리자가 숨긴 글도 status=HIDDEN 으로 같이) */
    public List<PostResponse> myPosts(Long id) {
        List<PostResponse> out = new ArrayList<>();
        for (Map<String, Object> r : jdbc.queryForList(
                "SELECT p.post_id, p.category, p.title, p.views, p.status, p.created_at, p.updated_at,"
                        + " (SELECT count(*) FROM post_comment c WHERE c.post_id = p.post_id AND NOT c.deleted) AS comment_count"
                        + " FROM post p WHERE p.author_id = :id AND p.status IN ('VISIBLE','HIDDEN') ORDER BY p.post_id DESC LIMIT :lim",
                Map.of("id", id, "lim", MY_LIST_MAX))) {
            String status = (String) r.get("status");
            out.add(new PostResponse(num(r.get("post_id")), PostService.label((String) r.get("category")), (String) r.get("title"), null, null,
                    List.of(), id, null, time(r.get("created_at")), time(r.get("updated_at")), (int) (long) num(r.get("views")),
                    num(r.get("comment_count")), null, "HIDDEN".equals(status) ? status : null, null));
        }
        return out;
    }

    /** GET /api/me/comments — 내가 쓴 댓글 (지운 댓글·숨긴 글의 댓글은 빼고, 최근 순) */
    public List<MyCommentResponse> myComments(Long id) {
        List<MyCommentResponse> out = new ArrayList<>();
        for (Map<String, Object> r : jdbc.queryForList(
                "SELECT c.comment_id, c.post_id, p.title, c.body, c.created_at FROM post_comment c JOIN post p ON p.post_id = c.post_id"
                        + " WHERE c.author_id = :id AND NOT c.deleted AND p.status = 'VISIBLE' ORDER BY c.comment_id DESC LIMIT :lim",
                Map.of("id", id, "lim", MY_LIST_MAX)))
            out.add(new MyCommentResponse(num(r.get("comment_id")), num(r.get("post_id")), (String) r.get("title"), (String) r.get("body"), time(r.get("created_at"))));
        return out;
    }

    /** 관심 품목 코드 (넣은 순서) */
    public List<String> favorites(Long id) {
        return jdbc.queryForList("SELECT item_code FROM user_favorite WHERE user_id = :id ORDER BY created_at, item_code", Map.of("id", id), String.class);
    }

    /**
     * PUT /api/me/favorites — 관심 품목 전체를 바꿈. 품목 코드는 DB item 표에 있는 것만 (없는 코드가 섞이면 422).
     * 순서는 보낸 순서 그대로 (화면 위쪽 카드 순서)
     */
    @Transactional
    public List<String> setFavorites(Long id, List<String> items) {
        user(id);
        LinkedHashSet<String> codes = new LinkedHashSet<>();
        for (String c : items == null ? List.<String>of() : items) {
            if (c == null || !c.matches("^[a-z_]{2,30}$")) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "품목 코드를 확인하세요");
            codes.add(c);
        }
        if (codes.size() > MAX_FAVORITES) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "관심 품목은 " + MAX_FAVORITES + "개까지 고를 수 있어요");
        if (!codes.isEmpty()) {
            List<String> known = jdbc.queryForList("SELECT item_code FROM item WHERE item_code IN (:c)", Map.of("c", codes), String.class);
            if (known.size() != codes.size()) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "없는 품목이 있어요");
        }
        // 11-16: 같은 회원의 저장이 동시에 두 번 오면(빠른 연속 클릭) 둘 다 지우고 넣다가 중복 키 500 이 났음 → 회원 줄을 잠가 차례로, 넣기는 겹쳐도 무시
        jdbc.queryForList("SELECT user_id FROM users WHERE user_id = :id FOR UPDATE", Map.of("id", id), Long.class); // 11-17: 열 이름 user_id (id 로 써서 저장마다 500 이었음)
        jdbc.update("DELETE FROM user_favorite WHERE user_id = :id", Map.of("id", id));
        LocalDateTime t = LocalDateTime.now();
        int i = 0;
        for (String c : codes)   // 넣은 순서를 created_at 으로 남김 (1ms 씩)
            jdbc.update("INSERT INTO user_favorite (user_id, item_code, created_at) VALUES (:id, :c, :t) ON CONFLICT (user_id, item_code) DO NOTHING",
                    Map.of("id", id, "c", c, "t", Timestamp.valueOf(t.plusNanos(1_000_000L * i++))));
        return favorites(id);
    }

    private static Long num(Object o) {
        return o == null ? null : ((Number) o).longValue();
    }

    private static LocalDateTime time(Object o) {
        if (o == null) return null;
        if (o instanceof Timestamp t) return t.toLocalDateTime();
        if (o instanceof LocalDateTime t) return t;
        return LocalDateTime.parse(o.toString().replace(' ', 'T'));
    }
}
