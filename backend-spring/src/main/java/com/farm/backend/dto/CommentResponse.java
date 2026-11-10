package com.farm.backend.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 댓글 응답 (명세서 2-10 과 같은 이름). 원댓글은 replies 에 답글 목록, 답글은 replies 없음.
 * deleted=true 면 body 는 "" (화면이 "삭제된 댓글입니다"로 보여줌)
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record CommentResponse(
        Long id,
        @JsonProperty("parent_id") Long parentId,
        Long author,
        @JsonProperty("author_name") String authorName,
        String body,
        @JsonProperty("created_at") LocalDateTime createdAt,
        boolean deleted,
        List<CommentResponse> replies
) {
}
