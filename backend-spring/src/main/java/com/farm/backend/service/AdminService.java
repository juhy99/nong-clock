package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.Admin;
import com.farm.backend.repository.AdminRepository;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 관리자 로그인 (11-14). 관리자 계정은 DB 표 admin (일반 회원 users 와 따로), 화면 없이 SQL 로 넣는다.
 * 비밀번호 확인은 회원과 같은 BCrypt. 실패 문장은 하나로 (어떤 이메일이 관리자인지 알 수 없게)
 */
@Service
@Transactional(readOnly = true)
public class AdminService {
    static final String LOGIN_FAIL = "이메일 또는 비밀번호가 맞지 않습니다";

    private final AdminRepository admins;
    private final PasswordEncoder passwordEncoder;
    private final String dummyHash; // 없는 이메일도 같은 시간이 걸리게

    public AdminService(AdminRepository admins, PasswordEncoder passwordEncoder) {
        this.admins = admins;
        this.passwordEncoder = passwordEncoder;
        this.dummyHash = passwordEncoder.encode("dummy-admin-password-1234");
    }

    public Admin login(String email, String password) {
        String e = email == null ? "" : email.trim();
        Admin a = e.isEmpty() ? null : admins.findByEmailIgnoreCase(e).orElse(null);
        boolean ok = passwordEncoder.matches(password == null ? "" : password, a == null ? dummyHash : a.getPasswordHash()) && a != null;
        if (!ok) throw new ApiException(HttpStatus.UNAUTHORIZED, LOGIN_FAIL);
        return a;
    }

    /** 세션의 관리자가 아직 있는지 (표에서 지웠으면 null → 로그아웃) */
    public Admin find(Long id) {
        return id == null ? null : admins.findById(id).orElse(null);
    }
}
