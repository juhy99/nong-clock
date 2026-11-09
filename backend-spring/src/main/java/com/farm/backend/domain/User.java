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

    // DB 는 users.region_id (시·도 번호 1~17, 수집기 ref/region.csv 와 같은 번호). 예전 'region' 글자 열은 표에 없어
    // ddl-auto: validate 에서 서버가 켜지지 않았다 (2026-11-09 고침). 화면은 지역 이름을 주고받고, 번호 변환은 UserService
    @Column(name = "region_id")
    private Integer regionId;

    @Column(name = "farm_name", length = 100)
    private String farmName; // 💡 농장·상호명 추가 (프론트의 farm_name)

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}