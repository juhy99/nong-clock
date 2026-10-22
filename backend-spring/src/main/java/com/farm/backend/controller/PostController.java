package com.farm.backend.controller;

import com.farm.backend.domain.Post;
import com.farm.backend.service.PostService;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/posts")
@RequiredArgsConstructor
public class PostController {

    private final PostService postService;

    // 게시글 작성 요청 DTO
    @Getter @Setter
    public static class PostRequest {
        private Long authorId;
        private String category;
        private String title;
        private String body;
    }

    /**
     * 게시글 작성 API (POST /api/posts)
     */
    @PostMapping
    public ResponseEntity<String> writePost(@RequestBody PostRequest request) {
        try {
            postService.writePost(request.getAuthorId(), request.getCategory(), request.getTitle(), request.getBody());
            return ResponseEntity.ok("게시글이 성공적으로 등록되었습니다.");
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    /**
     * 전체 게시글 목록 조회 API (GET /api/posts)
     */
    @GetMapping
    public ResponseEntity<List<Post>> getAllPosts() {
        List<Post> posts = postService.getAllPosts();
        return ResponseEntity.ok(posts);
    }
}