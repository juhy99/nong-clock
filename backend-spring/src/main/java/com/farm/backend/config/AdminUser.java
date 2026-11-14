package com.farm.backend.config;

import java.io.Serializable;

/**
 * 세션에 저장되는 "로그인한 관리자" (11-14, 비밀번호 없음). 일반 회원은 LoginUser.
 * 관리자 컨트롤러에서: {@code @AuthenticationPrincipal AdminUser admin} → admin.id()
 */
public record AdminUser(Long id, String email, String name) implements Serializable {
}
