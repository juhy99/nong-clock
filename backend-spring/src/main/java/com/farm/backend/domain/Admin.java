package com.farm.backend.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * 관리자 계정 (DB 표 admin, 11-14). 일반 회원(users)과 따로 — 관리자 사이트(/admin/)는 이 표로만 로그인한다.
 * 계정은 화면 없이 SQL 로 직접 넣는다 (deploy/README.md 1-2). passwordHash 는 BCrypt
 */
@Entity
@Table(name = "admin")
@Getter @Setter
@NoArgsConstructor
public class Admin {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "admin_id")
    private Long id;

    @Column(nullable = false, unique = true, length = 100)
    private String email;

    @Column(name = "password_hash", nullable = false, length = 100)
    private String passwordHash;

    @Column(nullable = false, length = 30)
    private String name;

    @Column(name = "created_at", nullable = false, updatable = false, insertable = false)
    private LocalDateTime createdAt;
}
