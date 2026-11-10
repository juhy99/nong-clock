package com.farm.backend.controller;

import com.farm.backend.config.LoginUser;
import com.farm.backend.dto.CommentRequest;
import com.farm.backend.dto.CommentResponse;
import com.farm.backend.service.CommentService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 댓글 API (명세서 2-10, 11-10)
 *   GET    /api/posts/{postId}/comments   댓글·답글 (누구나)                         200 · 404 없는 글
 *   POST   /api/posts/{postId}/comments   {"body", "parent_id"} 쓰기 (로그인 필수)   201 · 401 · 404 · 422
 *   DELETE /api/comments/{id}             지우기 (로그인 필수, 본인 댓글만)          204 · 401 · 403 · 404
 * 작성자는 로그인한 회원(세션)으로 정함. 오류는 {"message": "..."} (ApiExceptionHandler)
 */
@RestController
@RequestMapping("/api")
public class CommentController {

    private final CommentService commentService;

    public CommentController(CommentService commentService) {
        this.commentService = commentService;
    }

    @GetMapping("/posts/{postId}/comments")
    public List<CommentResponse> list(@PathVariable Long postId) {
        return commentService.list(postId);
    }

    @PostMapping("/posts/{postId}/comments")
    public ResponseEntity<CommentResponse> create(@AuthenticationPrincipal LoginUser me, @PathVariable Long postId,
                                                  @Valid @RequestBody CommentRequest body) {
        CommentResponse c = commentService.create(me.id(), postId, body.body(), body.parentId());
        return ResponseEntity.status(HttpStatus.CREATED).body(c);
    }

    @DeleteMapping("/comments/{id}")
    public ResponseEntity<Void> delete(@AuthenticationPrincipal LoginUser me, @PathVariable Long id) {
        commentService.delete(me.id(), id);
        return ResponseEntity.noContent().build();
    }
}
