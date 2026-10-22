package com.farm.backend.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import java.time.LocalDateTime;

@Entity
@Table(name = "users")
@Getter @Setter
@NoArgsConstructor
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "user_id")
    private Long id;

    @Column(nullable = false, unique = true, length = 100)
    private String email; // 로그인 아이디로 사용되는 이메일

    @Column(name = "password_hash", nullable = false, length = 100)
    private String passwordHash; // 암호화된 비밀번호

    @Column(nullable = false, length = 30)
    private String name; // 사용자 이름

    @Column(nullable = false, length = 20)
    private String phone; // 연락처

    @Column(length = 50)
    private String region; // 💡 지역 추가 (프론트의 region)

    @Column(name = "farm_name", length = 100)
    private String farmName; // 💡 농장·상호명 추가 (프론트의 farm_name)

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}