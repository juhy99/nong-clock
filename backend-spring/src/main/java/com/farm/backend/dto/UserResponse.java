package com.farm.backend.dto;

/**
 * 화면에 보내는 회원 정보 — 비밀번호(해시)는 절대 넣지 않는다.
 * 화면 auth.js fromSpring 이 type(MEMBER→member) · farmName→farm_name 으로 바꿔 씀
 */
public record UserResponse(
        Long id,
        String email,
        String name,
        String nickname,
        String phone,
        String region,
        String farmName,
        String type
) {
}
