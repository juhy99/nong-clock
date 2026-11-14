package com.farm.backend.config;

import com.farm.backend.domain.User;
import com.farm.backend.repository.UserRepository;
import com.farm.backend.service.UserService;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/** 관리자 지정 (11-14): ADMIN_EMAILS 에 있는 회원만 ADMIN, 빠진 회원은 MEMBER 로 되돌림. 응답 type 도 같이 바뀜 */
class AdminAccountsTest {

    static User user(String email, String role) {
        User u = new User();
        u.setEmail(email);
        u.setRole(role);
        return u;
    }

    @Test
    void parse_trims_lowercases_and_dedupes() {
        assertThat(AdminAccounts.parse(" Admin@Farm.kr, b@x.kr ,,admin@farm.kr")).containsExactly("admin@farm.kr", "b@x.kr");
        assertThat(AdminAccounts.parse("")).isEmpty();
        assertThat(AdminAccounts.parse(null)).isEmpty();
    }

    @Test
    void listed_become_admin_and_removed_become_member() {
        UserRepository repo = mock(UserRepository.class);
        User a = user("admin@farm.kr", User.ROLE_MEMBER), old = user("old@farm.kr", User.ROLE_ADMIN), m = user("m@farm.kr", User.ROLE_MEMBER);
        when(repo.findAll()).thenReturn(List.of(a, old, m));
        when(repo.findByEmail(anyString())).thenReturn(Optional.of(a));
        new AdminAccounts(repo, "Admin@farm.kr").run(null);
        assertThat(a.isAdmin()).isTrue();
        assertThat(old.isAdmin()).isFalse();
        assertThat(m.getRole()).isEqualTo(User.ROLE_MEMBER);
        verify(repo).save(a);
        verify(repo).save(old);
        verify(repo, never()).save(m);
        assertThat(UserService.toResponse(a).type()).isEqualTo("ADMIN");
        assertThat(UserService.toResponse(m).type()).isEqualTo("MEMBER");
    }

    @Test
    void empty_list_changes_nothing() {
        UserRepository repo = mock(UserRepository.class);
        new AdminAccounts(repo, "").run(null);
        verifyNoInteractions(repo);
    }
}
