package com.farm.backend.repository;

import com.farm.backend.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    // 이메일로 회원을 조회하는 커스텀 메서드 (로그인 및 중복 가입 방지용)
    Optional<User> findByEmail(String email);
}