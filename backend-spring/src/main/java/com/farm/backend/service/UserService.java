package com.farm.backend.service;

import com.farm.backend.domain.User;
import com.farm.backend.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    /**
     * 회원가입 로직
     */
    @Transactional
    public Long register(String email, String rawPassword, String name, String phone, String region, String farmName) {
        // 1. 이메일 중복 검사
        userRepository.findByEmail(email).ifPresent(user -> {
            throw new IllegalArgumentException("이미 가입된 이메일입니다.");
        });

        // 2. User 엔티티 생성 및 저장
        User user = new User();
        user.setEmail(email);
        user.setPasswordHash(rawPassword); // 또는 user.setPassword(rawPassword) (엔티티 필드명에 맞추세요)
        user.setName(name);
        user.setPhone(phone);
        user.setRegion(region);       // 💡 지역 추가
        user.setFarmName(farmName);   // 💡 농장명 추가

        userRepository.save(user);
        return user.getId();
    }

    /**
     * 로그인 로직
     */
    public User login(String email, String password) {
        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new IllegalArgumentException("존재하지 않는 이메일입니다."));

        if (!user.getPasswordHash().equals(password)) { // 엔티티 필드명 확인 필요
            throw new IllegalArgumentException("비밀번호가 일치하지 않습니다.");
        }

        return user;
    }
}