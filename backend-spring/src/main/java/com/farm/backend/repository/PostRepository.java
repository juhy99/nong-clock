package com.farm.backend.repository;

import com.farm.backend.domain.Post;
import org.springframework.data.jpa.repository.JpaRepository;

public interface PostRepository extends JpaRepository<Post, Long> {
    // 필요에 따라 카테고리별 조회나 최신순 정렬 등을 나중에 여기에 추가할 수 있습니다.
}