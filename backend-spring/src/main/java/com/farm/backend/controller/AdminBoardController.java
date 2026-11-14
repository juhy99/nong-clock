package com.farm.backend.controller;

import com.farm.backend.config.AdminUser;
import com.farm.backend.dto.CommentRequest;
import com.farm.backend.dto.CommentResponse;
import com.farm.backend.dto.PostPage;
import com.farm.backend.dto.PostRequest;
import com.farm.backend.dto.PostResponse;
import com.farm.backend.service.CommentService;
import com.farm.backend.service.PostService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 관리자 게시판 관리 (11-14) — 관리자 로그인(ROLE_ADMIN)만 (SecurityConfig /api/admin/**)
 *   GET    /api/admin/posts?category=&q=&status=VISIBLE|HIDDEN&page=   숨긴 글·공지 포함 목록 (status · hidden_reason)
 *   GET    /api/admin/posts/{id}                                       글 보기 (숨긴 글도)
 *   POST   /api/admin/posts        {"category","title","body"}          관리자 글쓰기 (말머리 "공지" 가능) 201 {"id"}
 *   PUT    /api/admin/posts/{id}   {"category","title","body"}          관리자 글 고치기 (회원 글은 403)
 *   PATCH  /api/admin/posts/{id}   {"hidden", "reason"}                 숨기기(사유 필수)·다시 보이기
 *   DELETE /api/admin/posts/{id}                                        누구 글이든 삭제 (댓글도 같이)
 *   GET    /api/admin/posts/{id}/comments                               댓글·답글 (숨긴 글도)
 *   POST   /api/admin/posts/{id}/comments  {"body","parent_id"}         관리자 댓글·답글 201
 *   DELETE /api/admin/comments/{id}                                     누구 댓글이든 삭제
 */
@RestController
@RequestMapping("/api/admin")
public class AdminBoardController {
    private static final int MAX_QUERY = 100;

    private final PostService postService;
    private final CommentService commentService;

    public AdminBoardController(PostService postService, CommentService commentService) {
        this.postService = postService;
        this.commentService = commentService;
    }

    public record HideRequest(boolean hidden, String reason) {
    }

    @GetMapping("/posts")
    public PostPage list(@RequestParam(required = false) String category, @RequestParam(required = false) String q,
                         @RequestParam(required = false) String status, @RequestParam(defaultValue = "1") int page) {
        if (q != null && q.length() > MAX_QUERY) q = q.substring(0, MAX_QUERY);
        return postService.adminList(category, q, status, page);
    }

    @GetMapping("/posts/{id}")
    public PostResponse get(@PathVariable Long id) {
        return postService.adminGet(id);
    }

    @PostMapping("/posts")
    public ResponseEntity<Map<String, Long>> write(@AuthenticationPrincipal AdminUser me, @Valid @RequestBody PostRequest body) {
        Long id = postService.adminWrite(me.id(), body.category(), body.title(), body.body());
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("id", id));
    }

    @PutMapping("/posts/{id}")
    public PostResponse update(@PathVariable Long id, @Valid @RequestBody PostRequest body) {
        return postService.adminUpdate(id, body.category(), body.title(), body.body());
    }

    @PatchMapping("/posts/{id}")
    public PostResponse hide(@AuthenticationPrincipal AdminUser me, @PathVariable Long id, @RequestBody HideRequest body) {
        return postService.setHidden(me.id(), id, body.hidden(), body.reason());
    }

    @DeleteMapping("/posts/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        postService.adminDelete(id);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/posts/{id}/comments")
    public List<CommentResponse> comments(@PathVariable Long id) {
        return commentService.adminList(id);
    }

    @PostMapping("/posts/{id}/comments")
    public ResponseEntity<CommentResponse> comment(@AuthenticationPrincipal AdminUser me, @PathVariable Long id, @Valid @RequestBody CommentRequest body) {
        return ResponseEntity.status(HttpStatus.CREATED).body(commentService.adminCreate(me.id(), id, body.body(), body.parentId()));
    }

    @DeleteMapping("/comments/{id}")
    public ResponseEntity<Void> deleteComment(@PathVariable Long id) {
        commentService.adminDelete(id);
        return ResponseEntity.noContent().build();
    }
}
