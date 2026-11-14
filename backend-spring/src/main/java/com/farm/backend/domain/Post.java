package com.farm.backend.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import java.time.LocalDateTime;

@Entity
@Table(name = "post")
@Getter @Setter
@NoArgsConstructor
public class Post {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "post_id")
    private Long id;

    @Column(name = "author_id")
    private Long authorId; // 작성자 회원 번호 (User의 id). 관리자 글이면 null

    @Column(name = "admin_id")
    private Long adminId; // 관리자가 쓴 글(공지 등)이면 관리자 번호 (11-14), 회원 글이면 null

    @Column(nullable = false, length = 20)
    private String category; // 말머리: FREE · QUESTION · INFO · REVIEW · NOTICE(공지, 관리자만 11-14) (DB CHECK 제약과 같음)

    @Column(nullable = false, length = 80)
    private String title; // 글 제목 (DB VARCHAR(80))

    @Column(nullable = false, columnDefinition = "TEXT")
    private String body; // 글 내용

    @Column(nullable = false)
    private Integer views = 0; // Long -> Integer로 변경

    /** VISIBLE(보임)·HIDDEN(관리자 숨김)·DELETED — DB 기본값 VISIBLE. 관리자가 숨기기·다시 보이기 (11-14) */
    @Column(length = 20, insertable = false)
    private String status;

    @Column(name = "hidden_reason", length = 200)
    private String hiddenReason; // 숨긴 사유 (관리자 사이트에만 보임)

    @Column(name = "hidden_by")
    private Integer hiddenBy; // 숨긴 관리자 번호

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();

    @Column(name = "updated_at")
    private LocalDateTime updatedAt; // 고친 때 (안 고쳤으면 null → 화면에 "(수정됨)" 없음)
}