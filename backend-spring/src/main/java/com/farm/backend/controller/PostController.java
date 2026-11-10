package com.farm.backend.controller;

import com.farm.backend.config.ApiException;
import com.farm.backend.config.LoginUser;
import com.farm.backend.dto.PostPage;
import com.farm.backend.dto.PostRequest;
import com.farm.backend.dto.PostResponse;
import com.farm.backend.service.PostService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.HashSet;
import java.util.Map;
import java.util.Set;

/**
 * 게시판 글 API (명세서 2-9, 11-10)
 *   GET    /api/posts?category=&q=&page=   목록 (누구나) — 보이는 글만, 15개씩
 *   GET    /api/posts/{id}?view=true       보기 (누구나) — view=true 면 조회수 +1, 같은 사람(세션)은 글마다 한 번만
 *   POST   /api/posts                      쓰기 (로그인)         201 {"id"} · 401 · 422
 *   PUT    /api/posts/{id}                 고치기 (본인만)       200 글 · 401 · 403 · 404 · 422
 *   DELETE /api/posts/{id}                 지우기 (본인만)       204 · 401 · 403 · 404  (댓글도 같이 지워짐)
 * 작성자는 요청 본문이 아니라 로그인한 회원(세션)으로 정한다. 오류는 {"message": "..."} (ApiExceptionHandler)
 */
@RestController
@RequestMapping("/api/posts")
public class PostController {
    private static final String VIEWED = "viewedPosts";

    private final PostService postService;

    public PostController(PostService postService) {
        this.postService = postService;
    }

    @GetMapping
    public PostPage list(@RequestParam(required = false) String category, @RequestParam(required = false) String q,
                         @RequestParam(defaultValue = "1") int page) {
        return postService.list(category, q, page);
    }

    @GetMapping("/{id}")
    public PostResponse get(@PathVariable Long id, @RequestParam(defaultValue = "false") boolean view, HttpServletRequest request) {
        return postService.get(id, view && firstView(request, id));
    }

    @PostMapping
    public ResponseEntity<Map<String, Long>> writePost(@AuthenticationPrincipal LoginUser me, @Valid @RequestBody PostRequest request) {
        noImages(request);
        Long id = postService.writePost(me.id(), request.category(), request.title(), request.body());
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("id", id));
    }

    @PutMapping("/{id}")
    public PostResponse update(@AuthenticationPrincipal LoginUser me, @PathVariable Long id, @Valid @RequestBody PostRequest request) {
        noImages(request);
        return postService.update(me.id(), id, request.category(), request.title(), request.body());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@AuthenticationPrincipal LoginUser me, @PathVariable Long id) {
        postService.delete(me.id(), id);
        return ResponseEntity.noContent().build();
    }

    /** 이 세션에서 이 글을 처음 보는지 (새로고침마다 조회수가 오르지 않게, 명세서 2-9 권장) */
    @SuppressWarnings("unchecked")
    private static boolean firstView(HttpServletRequest request, Long id) {
        HttpSession session = request.getSession(true);
        Set<Long> seen = (Set<Long>) session.getAttribute(VIEWED);
        if (seen == null) seen = new HashSet<>();
        boolean first = seen.add(id);
        session.setAttribute(VIEWED, seen);
        return first;
    }

    private static void noImages(PostRequest request) {
        if (request.images() != null && !request.images().isEmpty())
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "사진 첨부는 아직 준비 중이에요");
    }
}
