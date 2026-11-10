package com.farm.backend.dto;

import java.util.List;

/** GET /api/posts 응답: { rows, total(전체 글 수), page(지금 쪽), pages(전체 쪽 수) } */
public record PostPage(List<PostResponse> rows, long total, int page, int pages) {
}
