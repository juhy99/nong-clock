package com.farm.backend.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** POST /api/posts/{id}/comments 요청 (명세서 2-10). parent_id 가 있으면 답글. 작성자는 받지 않음 (세션 회원) */
public record CommentRequest(
        @NotBlank(message = "댓글 내용을 입력하세요")
        @Size(max = 2000, message = "댓글은 500자까지 쓸 수 있습니다") // 앞뒤 공백을 뺀 500자 검사는 CommentService
        String body,

        @JsonProperty("parent_id") @JsonAlias("parentId")
        Long parentId
) {
}
