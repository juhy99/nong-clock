package com.farm.backend.repository;

import com.farm.backend.domain.Post;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface PostRepository extends JpaRepository<Post, Long> {
    /** 회원 탈퇴 때 그 회원이 쓴 글 전부 지우기 (UserService.withdraw, 트랜잭션 안에서 부름) */
    @Modifying
    @Query("delete from Post p where p.authorId = :authorId")
    int deleteByAuthorId(@Param("authorId") Long authorId);
}
