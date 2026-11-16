package com.farm.backend.dto;

import java.util.List;

/** PUT /api/me/favorites 요청 (11-16, 명세서 2-8): 관심 품목 전체를 이 목록으로 바꿈 (품목 코드, 최대 50개) */
public record FavoritesRequest(List<String> items) {
}
