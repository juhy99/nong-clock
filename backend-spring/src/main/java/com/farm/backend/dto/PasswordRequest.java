package com.farm.backend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

/** PUT /api/me/password 요청 (11-16, 명세서 2-7): 지금 비밀번호 확인 뒤 새 비밀번호로. 새 비밀번호 규칙은 가입(SignupRequest)과 같음 */
public record PasswordRequest(
        @NotBlank(message = "지금 비밀번호를 입력하세요")
        String current,

        @NotBlank(message = "새 비밀번호를 입력하세요")
        @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d)[\\x21-\\x7E]{8,64}$", message = "비밀번호는 영문과 숫자를 섞어 8~64자로 입력하세요 (한글·띄어쓰기 없이)")
        String next
) {
}
