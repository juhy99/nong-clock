package com.farm.backend.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import java.time.LocalDateTime;

/**
 * 댓글·답글 (DB 표 post_comment, 11-10). parentId 가 있으면 그 댓글의 답글.
 * 표는 resources/db/post_comment.sql 이 서버 시작 때 만든다 (없을 때만).
 * deleted: 답글이 달린 댓글을 지울 때 "삭제된 댓글입니다"로 남기는 표시 (명세서 2-10). 댓글 API 를 만들 때 사용
 */
@Entity
@Table(name = "post_comment")
@Getter @Setter
@NoArgsConstructor
public class PostComment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "comment_id")
    private Long id;

    @Column(name = "post_id", nullable = false)
    private Long postId;

    @Column(name = "parent_id")
    private Long parentId;

    @Column(name = "author_id", nullable = false)
    private Long authorId; // 로그인한 회원(세션) 번호만 넣을 것

    @Column(nullable = false, columnDefinition = "TEXT")
    private String body;

    @Column(nullable = false)
    private boolean deleted;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}
