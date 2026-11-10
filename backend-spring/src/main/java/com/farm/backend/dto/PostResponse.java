package com.farm.backend.dto;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 게시글 응답 (명세서 2-9 와 같은 이름). category 는 화면 이름(자유·질문·정보·거래후기).
 * 목록: body 없음, 검색할 때 snippet(본문 일부). 보기: body 있음. 값이 없는 칸(null)은 응답에서 빠짐
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record PostResponse(
        Long id,
        String category,
        String title,
        String body,
        String snippet,
        List<String> images,
        Long author,
        @JsonProperty("author_name") String authorName,
        @JsonProperty("created_at") LocalDateTime createdAt,
        @JsonProperty("updated_at") LocalDateTime updatedAt,
        Integer views,
        @JsonProperty("comment_count") Long commentCount
) {
}
