package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.Admin;
import com.farm.backend.repository.AdminRepository;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/** 관리자 로그인 (11-14): admin 표 계정만, BCrypt. pgcrypto crypt(…, gen_salt('bf')) 로 넣은 $2a$ 값도 맞아야 함 */
class AdminServiceTest {
    // PostgreSQL: SELECT crypt('admin1234!', gen_salt('bf', 10)) 로 만든 값 (SQL 로 넣는 방식과 같음)
    static final String PG_HASH = "$2a$10$SMtzfSgOt3kqcakonWrIdeBy0o7znadT6jkhTZpBegk5kAGq1r2iC";

    static AdminService service(Admin a) {
        AdminRepository repo = mock(AdminRepository.class);
        when(repo.findByEmailIgnoreCase(anyString())).thenReturn(Optional.empty());
        if (a != null) when(repo.findByEmailIgnoreCase(a.getEmail())).thenReturn(Optional.of(a));
        return new AdminService(repo, new BCryptPasswordEncoder());
    }

    static Admin admin() {
        Admin a = new Admin();
        a.setId(1L);
        a.setEmail("admin@nongclock.kr");
        a.setName("운영자");
        a.setPasswordHash(PG_HASH);
        return a;
    }

    @Test
    void sql_bcrypt_hash_logs_in() {
        assertThat(service(admin()).login(" admin@nongclock.kr ", "admin1234!").getName()).isEqualTo("운영자");
    }

    @Test
    void wrong_password_or_unknown_email_same_message() {
        AdminService s = service(admin());
        assertThatThrownBy(() -> s.login("admin@nongclock.kr", "nope")).isInstanceOf(ApiException.class).hasMessage(AdminService.LOGIN_FAIL);
        assertThatThrownBy(() -> s.login("member@test.kr", "admin1234!")).isInstanceOf(ApiException.class).hasMessage(AdminService.LOGIN_FAIL);
        assertThatThrownBy(() -> s.login("", "")).isInstanceOf(ApiException.class);
    }
}
