package com.farm.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** POST /api/auth/login 요청 */
public record LoginRequest(
        @NotBlank(message = "이메일을 입력하세요")
        @Size(max = 100, message = "이메일 또는 비밀번호가 맞지 않습니다")
        String email,

        @NotBlank(message = "비밀번호를 입력하세요")
        @Size(max = 64, message = "이메일 또는 비밀번호가 맞지 않습니다")
        String password
) {
}
