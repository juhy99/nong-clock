package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.Post;
import com.farm.backend.domain.User;
import com.farm.backend.dto.PostPage;
import com.farm.backend.dto.PostResponse;
import com.farm.backend.repository.PostRepository;
import com.farm.backend.repository.PriceSql;
import com.farm.backend.repository.UserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 게시판 글 (명세서 2-9, 11-10). 화면 가짜 데이터(frontend/src/api/board.js)와 같은 규칙:
 * - 목록: 보이는 글(VISIBLE)만, 최신순 15개씩, 말머리·검색어(제목·내용·닉네임), 댓글 수(지운 댓글 빼고), 검색하면 본문 일부
 * - 쓰기·고치기: 제목 2~80자, 내용 5자 이상 (앞뒤 공백 뺀 길이), 말머리 4가지
 * - 고치기·지우기: 작성자 본인만. 지우면 댓글도 같이 (DB ON DELETE CASCADE)
 * - 작성자는 늘 로그인한 회원(세션) 번호 — 컨트롤러가 넘겨줌
 * - 관리자(11-14): admin 표 계정이 공지·글·댓글을 쓰고(admin_id), 회원 글을 숨기기·다시 보이기·삭제 (/api/admin/posts…)
 * 아직 없는 것: 사진 첨부(업로드 API·사진 열 없음), 게시판 이용 제한
 */
@Service
@Transactional(readOnly = true)
public class PostService {
    public static final int PAGE_SIZE = 15;

    /** DB 값 → 화면 이름 (명세서 2-9). 공지(NOTICE)는 관리자만 쓰는 말머리 (11-14) */
    static final Map<String, String> LABEL = Map.of("FREE", "자유", "QUESTION", "질문", "INFO", "정보", "REVIEW", "거래후기", "NOTICE", "공지");
    static final Map<String, String> CODE = Map.of("자유", "FREE", "질문", "QUESTION", "정보", "INFO", "거래후기", "REVIEW", "공지", "NOTICE");
    static final String NOTICE = "NOTICE";
    static final String ADMIN_NAME = "관리자"; // 관리자 글·댓글의 작성자 이름 (사용자 사이트에 보이는 이름)

    private final PostRepository postRepository;
    private final UserService userService;
    private final UserRepository userRepository;
    private final PriceSql sql; // 목록·검색은 SQL 로 (이름은 시세용이지만 "SELECT → 행 목록" 일반 도구)

    public PostService(PostRepository postRepository, UserService userService, UserRepository userRepository, PriceSql sql) {
        this.postRepository = postRepository;
        this.userService = userService;
        this.userRepository = userRepository;
        this.sql = sql;
    }

    /** 화면 이름이나 DB 값 → DB 값. 모르는 값이면 null */
    static String code(String category) {
        if (category == null) return null;
        String c = category.trim();
        return LABEL.containsKey(c) ? c : CODE.get(c);
    }

    static String label(String code) {
        return LABEL.getOrDefault(code, code);
    }

    /** LIKE 검색어에서 %, _, \ 를 글자 그대로 찾게 바꿈 */
    static String likePattern(String keyword) {
        return "%" + keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%";
    }

    /** 검색 결과에 보여줄 본문 일부 (검색어 앞 20자부터 70자) — 화면 board.js snippetOf 와 같음 */
    static String snippet(String body, String keyword) {
        if (body == null) return "";
        int at = body.toLowerCase(Locale.ROOT).indexOf(keyword);
        int start = at < 0 ? 0 : Math.max(0, at - 20);
        int end = Math.min(body.length(), start + 70);
        return (start > 0 ? "…" : "") + body.substring(start, end) + (end < body.length() ? "…" : "");
    }

    // 목록 SQL (PostgreSQL 에서 시험함). WHERE 는 조건이 있을 때만 붙임
    // 회원 목록은 공지(NOTICE)를 빼고 보여 준다 — 공지는 GET /api/notices 로 맨 위에 따로 (11-14)
    static final String LIST_FROM = " FROM post p LEFT JOIN users u ON u.user_id = p.author_id WHERE p.status = 'VISIBLE' AND p.category <> 'NOTICE'";
    static final String LIST_COLS = "SELECT p.post_id, p.category, p.title, p.body, p.author_id, p.admin_id, p.status, p.hidden_reason,"
            + " CASE WHEN p.admin_id IS NOT NULL THEN '" + "관리자" + "' ELSE u.name END AS author_name, p.created_at, p.updated_at, p.views,"
            + " (SELECT count(*) FROM post_comment c WHERE c.post_id = p.post_id AND NOT c.deleted) AS comment_count";
    // 관리자 목록: 숨긴 글·공지 포함 (11-14)
    static final String ADMIN_FROM = " FROM post p LEFT JOIN users u ON u.user_id = p.author_id WHERE p.status IN ('VISIBLE','HIDDEN')";

    /** GET /api/posts?category=&q=&page= (회원 사이트: 보이는 글, 공지 빼고) */
    public PostPage list(String category, String q, int page) {
        return page(LIST_FROM, category, q, page, false);
    }

    /** GET /api/admin/posts?category=&q=&status=&page= (관리자: 숨긴 글·공지 포함, 상태·숨긴 사유도) */
    public PostPage adminList(String category, String q, String status, int page) {
        String from = ADMIN_FROM;
        if ("HIDDEN".equals(status) || "VISIBLE".equals(status)) from += " AND p.status = '" + status + "'";
        return page(from, category, q, page, true);
    }

    /** GET /api/notices: 보이는 공지 전부 (최신순, 게시판 맨 위·통합 검색) */
    public List<PostResponse> notices() {
        List<PostResponse> out = new ArrayList<>();
        for (Map<String, Object> r : sql.rows(LIST_COLS + " FROM post p LEFT JOIN users u ON u.user_id = p.author_id"
                + " WHERE p.status = 'VISIBLE' AND p.category = 'NOTICE' ORDER BY p.post_id DESC LIMIT 20", Map.of()))
            out.add(row(r, null, false, true));
        return out;
    }

    private PostPage page(String from, String category, String q, int page, boolean admin) {
        Map<String, Object> params = new HashMap<>();
        StringBuilder where = new StringBuilder(from);
        if (category != null && !category.isBlank()) {
            String c = code(category);
            if (c == null) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "말머리를 확인하세요");
            where.append(" AND p.category = :cat");
            params.put("cat", c);
        }
        String kw = q == null ? "" : q.trim().toLowerCase(Locale.ROOT);
        if (!kw.isEmpty()) {
            where.append(" AND (lower(p.title) LIKE :kw ESCAPE '\\' OR lower(p.body) LIKE :kw ESCAPE '\\' OR lower(u.name) LIKE :kw ESCAPE '\\')");
            params.put("kw", likePattern(kw));
        }
        long total = ((Number) sql.rows("SELECT count(*) AS n" + where, params).get(0).get("n")).longValue();
        int pages = (int) Math.max(1, (total + PAGE_SIZE - 1) / PAGE_SIZE);
        int cur = Math.min(Math.max(1, page), pages);
        params.put("lim", PAGE_SIZE);
        params.put("off", (cur - 1) * PAGE_SIZE);
        List<PostResponse> rows = new ArrayList<>();
        for (Map<String, Object> r : sql.rows(LIST_COLS + where + " ORDER BY p.post_id DESC LIMIT :lim OFFSET :off", params))
            rows.add(row(r, kw, admin, false));
        return new PostPage(rows, total, cur, pages);
    }

    /** 목록 한 줄. withBody 면 본문 전체(공지), 검색어가 있으면 본문 일부 */
    private static PostResponse row(Map<String, Object> r, String kw, boolean admin, boolean withBody) {
        String body = (String) r.get("body");
        boolean byAdmin = r.get("admin_id") != null;
        return new PostResponse(num(r.get("post_id")), label((String) r.get("category")), (String) r.get("title"), withBody ? body : null,
                kw == null || kw.isEmpty() ? null : snippet(body, kw), List.of(), num(r.get("author_id")), nameOr((String) r.get("author_name")),
                time(r.get("created_at")), time(r.get("updated_at")), (int) (long) num(r.get("views")), num(r.get("comment_count")),
                byAdmin ? Boolean.TRUE : null, admin ? (String) r.get("status") : null, admin ? (String) r.get("hidden_reason") : null);
    }

    /** GET /api/posts/{id}. countView 면 조회수 +1 (같은 사람 반복은 컨트롤러가 세션으로 막음) */
    @Transactional
    public PostResponse get(Long id, boolean countView) {
        Post p = visiblePost(id);
        if (countView) p.setViews(p.getViews() + 1);
        return detail(p);
    }

    /** POST /api/posts. authorId 는 세션 회원 번호 */
    @Transactional
    public Long writePost(Long authorId, String category, String title, String body) {
        if (userService.findUser(authorId) == null)
            throw new ApiException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다");
        Post post = new Post();
        post.setAuthorId(authorId);
        fill(post, category, title, body, false);
        post.setViews(0);
        postRepository.save(post);
        return post.getId();
    }

    /** PUT /api/posts/{id}: 작성자 본인만 */
    @Transactional
    public PostResponse update(Long userId, Long id, String category, String title, String body) {
        Post p = visiblePost(id);
        if (!Objects.equals(p.getAuthorId(), userId)) throw new ApiException(HttpStatus.FORBIDDEN, "본인 글만 고칠 수 있습니다");
        fill(p, category, title, body, false);
        p.setUpdatedAt(LocalDateTime.now());
        postRepository.save(p);
        return detail(p);
    }

    /** DELETE /api/posts/{id}: 작성자 본인만. 댓글은 DB 가 같이 지움 */
    @Transactional
    public void delete(Long userId, Long id) {
        Post p = id == null ? null : postRepository.findById(id).orElse(null);
        if (p == null) throw new ApiException(HttpStatus.NOT_FOUND, "이미 지워진 글입니다");
        if (!Objects.equals(p.getAuthorId(), userId)) throw new ApiException(HttpStatus.FORBIDDEN, "본인 글만 지울 수 있습니다");
        postRepository.delete(p);
    }

    // ── 관리자 (11-14, /api/admin/posts…) ──

    /** 관리자 글 보기: 숨긴 글도, 상태·숨긴 사유 포함 */
    public PostResponse adminGet(Long id) {
        return detail(anyPost(id), true);
    }

    /** 관리자 글쓰기 (공지 포함). 작성자 = 관리자 번호 */
    @Transactional
    public Long adminWrite(Long adminId, String category, String title, String body) {
        Post post = new Post();
        post.setAdminId(adminId);
        fill(post, category, title, body, true);
        post.setViews(0);
        postRepository.save(post);
        return post.getId();
    }

    /** 관리자가 쓴 글만 관리자 사이트에서 고침 (회원 글은 내용을 바꾸지 않고 숨기기·삭제만) */
    @Transactional
    public PostResponse adminUpdate(Long id, String category, String title, String body) {
        Post p = anyPost(id);
        if (p.getAdminId() == null) throw new ApiException(HttpStatus.FORBIDDEN, "회원 글은 고칠 수 없어요 (숨기기·삭제만)");
        fill(p, category, title, body, true);
        p.setUpdatedAt(LocalDateTime.now());
        postRepository.save(p);
        return detail(p, true);
    }

    /** 숨기기·다시 보이기. 숨길 때는 사유 필수 */
    @Transactional
    public PostResponse setHidden(Long adminId, Long id, boolean hidden, String reason) {
        Post p = anyPost(id);
        String why = reason == null ? "" : reason.trim();
        if (hidden && why.isEmpty()) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "숨기는 사유를 적어 주세요");
        if (why.length() > 200) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "사유는 200자까지 쓸 수 있습니다");
        p.setStatus(hidden ? "HIDDEN" : "VISIBLE");
        p.setHiddenReason(hidden ? why : null);
        p.setHiddenBy(hidden ? adminId.intValue() : null);
        postRepository.save(p);
        return detail(p, true);
    }

    /** 관리자 삭제 (누구 글이든). 댓글은 DB 가 같이 지움 */
    @Transactional
    public void adminDelete(Long id) {
        postRepository.delete(anyPost(id));
    }

    private Post anyPost(Long id) {
        Post p = id == null ? null : postRepository.findById(id).orElse(null);
        if (p == null || "DELETED".equals(p.getStatus())) throw new ApiException(HttpStatus.NOT_FOUND, "이미 지워진 글입니다");
        return p;
    }

    /**
     * 전체 게시글 목록 (예전 GET /api/posts 가 쓰던 것, 지금은 관리자용으로 남김)
     */
    public List<Post> getAllPosts() {
        return postRepository.findAll();
    }

    private Post visiblePost(Long id) {
        Post p = id == null ? null : postRepository.findById(id).orElse(null);
        if (p == null || (p.getStatus() != null && !"VISIBLE".equals(p.getStatus())))
            throw new ApiException(HttpStatus.NOT_FOUND, "삭제되었거나 볼 수 없는 글입니다");
        return p;
    }

    private static void fill(Post p, String category, String title, String body, boolean admin) {
        String c = code(category);
        if (c == null || (NOTICE.equals(c) && !admin)) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "말머리를 고르세요");
        String t = title == null ? "" : title.trim(), b = body == null ? "" : body.trim();
        if (t.length() < 2) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "제목을 2자 이상 입력하세요");
        if (t.length() > 80) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "제목은 80자까지 쓸 수 있습니다");
        if (b.length() < 5) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "내용을 5자 이상 입력하세요");
        p.setCategory(c);
        p.setTitle(t);
        p.setBody(b);
    }

    private PostResponse detail(Post p) {
        return detail(p, false);
    }

    private PostResponse detail(Post p, boolean admin) {
        boolean byAdmin = p.getAdminId() != null;
        User author = byAdmin || p.getAuthorId() == null ? null : userRepository.findById(p.getAuthorId()).orElse(null);
        Map<String, Object> params = Map.of("id", p.getId());
        long comments = num(sql.rows("SELECT count(*) AS n FROM post_comment WHERE post_id = :id AND NOT deleted", params).get(0).get("n"));
        return new PostResponse(p.getId(), label(p.getCategory()), p.getTitle(), p.getBody(), null, List.of(), p.getAuthorId(),
                byAdmin ? ADMIN_NAME : nameOr(author == null ? null : author.getName()), p.getCreatedAt(), p.getUpdatedAt(), p.getViews(), comments,
                byAdmin ? Boolean.TRUE : null, admin ? p.getStatus() : null, admin ? p.getHiddenReason() : null);
    }

    private static String nameOr(String name) {
        return name == null ? "알 수 없음" : name;
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
