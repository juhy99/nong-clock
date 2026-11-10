package com.farm.backend.controller;

import com.farm.backend.config.LoginUser;
import com.farm.backend.domain.Post;
import com.farm.backend.dto.PostRequest;
import com.farm.backend.service.PostService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 게시판 API.
 * 11-10 보안: 글쓰기의 작성자를 요청 본문(authorId)이 아니라 로그인한 회원(세션)으로 정한다.
 *   예전에는 authorId 를 아무 번호나 보내면 남의 이름으로 글을 쓸 수 있었다.
 *   POST /api/posts 는 로그인 필수 (SecurityConfig). 오류는 {"message": "..."} (ApiExceptionHandler)
 */
@RestController
@RequestMapping("/api/posts")
public class PostController {

    private final PostService postService;

    public PostController(PostService postService) {
        this.postService = postService;
    }

    /** 게시글 작성 (POST /api/posts) → 201 {"id": 새 글 번호} · 401 로그인 필요 · 422 입력 오류 */
    @PostMapping
    public ResponseEntity<Map<String, Long>> writePost(@AuthenticationPrincipal LoginUser me, @Valid @RequestBody PostRequest request) {
        Long id = postService.writePost(me.id(), request.category(), request.title().trim(), request.body());
        return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("id", id));
    }

    /** 전체 게시글 목록 조회 (GET /api/posts) — 누구나 */
    @GetMapping
    public ResponseEntity<List<Post>> getAllPosts() {
        return ResponseEntity.ok(postService.getAllPosts());
    }
}
