package com.farm.backend.repository;

import com.farm.backend.domain.User;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {
    /** 이메일은 소문자로 저장하므로 소문자로 바꿔서 찾기 (UserService.normEmail) */
    Optional<User> findByEmail(String email);

    boolean existsByEmail(String email);

    /** 닉네임 중복: 대소문자 구분 없이 ("Farmer" 와 "farmer" 는 같은 닉네임) */
    boolean existsByNameIgnoreCase(String name);
}
