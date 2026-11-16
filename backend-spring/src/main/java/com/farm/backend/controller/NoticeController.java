package com.farm.backend.controller;

import com.farm.backend.dto.PostResponse;
import com.farm.backend.service.PostService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 공지 (11-14): 관리자가 게시판 관리에서 말머리 "공지"로 쓴 글. 누구나 읽음
 *   GET /api/notices  보이는 공지 최신순 20개 (본문 포함) — 게시판 맨 위 · 통합 검색. 글 보기는 GET /api/posts/{id}
 */
@RestController
public class NoticeController {
    private final PostService postService;

    public NoticeController(PostService postService) {
        this.postService = postService;
    }

    @GetMapping("/api/notices")
    public List<PostResponse> notices() {
        return postService.notices();
    }
}
