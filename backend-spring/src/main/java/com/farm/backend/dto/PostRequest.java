package com.farm.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.util.List;

/**
 * 글쓰기·수정 요청 POST /api/posts, PUT /api/posts/{id} (명세서 2-9). 작성자 번호는 받지 않는다 — 로그인한 회원(세션)으로 정함.
 * category: 화면 이름(자유·질문·정보·거래후기) 또는 DB 값(FREE·QUESTION·INFO·REVIEW) 둘 다 받음.
 * 제목 2~80자·내용 5자 이상(앞뒤 공백 뺀 길이)은 PostService 에서 검사. images: 사진 첨부는 아직 준비 중 (있으면 422)
 */
public record PostRequest(
        @NotBlank(message = "말머리를 고르세요")
        String category,

        @NotBlank(message = "제목을 입력하세요")
        @Size(max = 200, message = "제목은 80자까지 쓸 수 있습니다")
        String title,

        @NotBlank(message = "내용을 입력하세요")
        @Size(max = 20000, message = "내용은 20,000자까지 쓸 수 있어요")
        String body,

        List<String> images
) {
}
