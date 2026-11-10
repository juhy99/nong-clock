package com.farm.backend.config;

import java.io.Serializable;

/**
 * 세션에 저장되는 "로그인한 회원" (비밀번호 없음).
 * 컨트롤러에서 꺼내 쓰기: {@code public ... myApi(@AuthenticationPrincipal LoginUser me)} → me.id()
 * 로그인 안 했으면 me 는 null (로그인 필수 주소는 SecurityConfig 에서 401 로 막힘)
 */
public record LoginUser(Long id, String email) implements Serializable {
}
