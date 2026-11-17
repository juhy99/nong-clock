package com.farm.backend.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * PATCH /api/me 요청 (11-16, 명세서 2-6): 내 정보 수정. 이메일은 바꿀 수 없음.
 * 닉네임(name 열)은 한글·영문·숫자 2~12자·중복 불가 (11-17) (UserService.normNickname 과 같은 규칙), 지역은 시·도 이름
 */
public record ProfileRequest(
        String nickname,
        String name,

        @NotBlank(message = "휴대폰 번호를 입력하세요")
        @Pattern(regexp = "^01\\d-\\d{3,4}-\\d{4}$", message = "휴대폰 번호를 확인하세요 (예: 010-1234-5678)")
        String phone,

        @NotBlank(message = "지역을 선택하세요")
        String region,

        @JsonAlias("farm_name")
        @Size(max = 50, message = "농장·상호명은 50자까지 입력할 수 있어요")
        String farmName
) {
}
