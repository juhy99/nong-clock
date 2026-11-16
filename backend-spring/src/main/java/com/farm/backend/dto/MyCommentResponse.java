package com.farm.backend.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;

/** GET /api/me/comments 한 줄 (11-16): 내가 쓴 댓글 + 그 글 제목 (마이페이지 '내가 쓴 댓글') */
public record MyCommentResponse(
        Long id,
        @JsonProperty("post_id") Long postId,
        @JsonProperty("post_title") String postTitle,
        String body,
        @JsonProperty("created_at") LocalDateTime createdAt
) {
}
