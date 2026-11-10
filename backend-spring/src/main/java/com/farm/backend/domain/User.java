package com.farm.backend.domain;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import java.time.LocalDateTime;

/**
 * 회원 (DB 표 users, db/init/farm_table.sql).
 * name 열 = 화면의 닉네임 (11-07 결정: 이름 대신 닉네임 2~20자, 중복 불가)
 * passwordHash 는 BCrypt 암호화 값만 들어감 (11-10). 이 객체를 그대로 응답으로 보내지 말 것 → UserService.toResponse
 */
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
    private String email; // 로그인 아이디 (소문자로 저장)

    @Column(name = "password_hash", nullable = false, length = 100)
    private String passwordHash; // BCrypt 암호화 값 (60자)

    @Column(nullable = false, length = 30)
    private String name; // 닉네임

    @Column(nullable = false, length = 20)
    private String phone; // 010-1234-5678

    // DB 는 users.region_id (시·도 번호 1~17, 수집기 ref/region.csv 와 같은 번호). 화면은 지역 이름을 주고받고, 번호 변환은 UserService
    @Column(name = "region_id")
    private Integer regionId;

    @Column(name = "farm_name", length = 50)
    private String farmName; // 농장·상호명 (선택)

    @Column(name = "marketing_agree", nullable = false)
    private boolean marketingAgree;

    /** ACTIVE(정상) · SUSPENDED(정지) · WITHDRAWN(탈퇴) — DB CHECK 제약과 같은 값 */
    @Column(nullable = false, length = 20)
    private String status = "ACTIVE";

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
}
