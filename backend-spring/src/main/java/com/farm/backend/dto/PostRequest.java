package com.farm.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * POST /api/posts 요청 (11-10). 작성자 번호는 받지 않는다 — 로그인한 회원(세션)으로 정함.
 * 말머리·길이는 DB 표 post 의 제약(db/init/farm_table.sql)과 같게: category 4가지, title 80자
 */
public record PostRequest(
        @NotBlank(message = "말머리를 고르세요")
        @Pattern(regexp = "FREE|QUESTION|INFO|REVIEW", message = "말머리를 고르세요")
        String category,

        @NotBlank(message = "제목을 입력하세요")
        @Size(max = 80, message = "제목은 80자까지 쓸 수 있어요")
        String title,

        @NotBlank(message = "내용을 입력하세요")
        @Size(max = 20000, message = "내용은 20,000자까지 쓸 수 있어요")
        String body
) {
}
