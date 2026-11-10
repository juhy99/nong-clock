package com.farm.backend.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * POST /api/auth/signup 요청 (명세서 2-3). 화면 Signup.jsx 와 같은 규칙을 서버에서도 한 번 더 검사한다
 * (화면 검사는 브라우저에서 우회할 수 있으므로 서버 검사가 진짜).
 * nickname 이 없으면 name 을 닉네임으로 씀 (화면이 지금 name 에도 같은 값을 보냄). 길이·중복은 UserService 에서 검사
 */
public record SignupRequest(
        @NotBlank(message = "이메일을 입력하세요")
        @Email(message = "올바른 이메일 형식이 아닙니다")
        @Size(max = 100, message = "이메일이 너무 깁니다")
        String email,

        @NotBlank(message = "비밀번호를 입력하세요")
        // 영문·숫자·기호(키보드 문자)만, 8~64자. BCrypt 는 앞 72바이트만 쓰므로 한글(글자당 3바이트)은 받지 않음
        @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d)[\\x21-\\x7E]{8,64}$", message = "비밀번호는 영문과 숫자를 섞어 8~64자로 입력하세요 (한글·띄어쓰기 없이)")
        String password,

        String nickname,
        String name,

        @NotBlank(message = "휴대폰 번호를 입력하세요")
        @Pattern(regexp = "^01\\d-\\d{3,4}-\\d{4}$", message = "휴대폰 번호를 확인하세요 (예: 010-1234-5678)")
        String phone,

        @NotBlank(message = "지역을 선택하세요")
        String region,

        @JsonAlias("farm_name")
        @Size(max = 50, message = "농장·상호명은 50자까지 입력할 수 있어요")
        String farmName,

        Boolean marketing
) {
}
