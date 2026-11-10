package com.farm.backend.dto;

/** DELETE /api/me 요청: 탈퇴 전에 비밀번호 한 번 더 확인 */
public record WithdrawRequest(String password) {
}
