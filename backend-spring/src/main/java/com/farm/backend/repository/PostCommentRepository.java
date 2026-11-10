package com.farm.backend.repository;

import com.farm.backend.domain.PostComment;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;

public interface PostCommentRepository extends JpaRepository<PostComment, Long> {
    /** 한 글의 댓글·답글 전부 (오래된 순) */
    List<PostComment> findByPostIdOrderByIdAsc(Long postId);

    /** 이 댓글에 지워지지 않은 답글이 있는지 */
    boolean existsByParentIdAndDeletedFalse(Long parentId);

    /** 회원 탈퇴 때 그 회원이 쓴 댓글 전부 지우기. 그 댓글에 달린 남의 답글은 DB 가 같이 지움 (ON DELETE CASCADE) */
    @Modifying
    @Query("delete from PostComment c where c.authorId = :authorId")
    int deleteByAuthorId(@Param("authorId") Long authorId);
}
