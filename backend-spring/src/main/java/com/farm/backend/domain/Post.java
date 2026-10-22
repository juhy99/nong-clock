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

    @Column(name = "author_id", nullable = false)
    private Long authorId; // 작성자 회원 번호 (User의 id)

    @Column(nullable = false, length = 50)
    private String category; // 카테고리 (예: 자유게시판, 묻고답하기 등)

    @Column(nullable = false, length = 200)
    private String title; // 글 제목

    @Column(nullable = false, columnDefinition = "TEXT")
    private String body; // 글 내용

    @Column(nullable = false)
    private Integer views = 0; // Long -> Integer로 변경

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}