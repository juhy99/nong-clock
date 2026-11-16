package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.User;
import com.farm.backend.dto.PasswordRequest;
import com.farm.backend.dto.ProfileRequest;
import com.farm.backend.repository.UserRepository;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** 마이페이지 (11-16): 내 정보 수정 · 비밀번호 변경 · 관심 품목 입력 검사 (DB 없이) */
class MyPageServiceTest {
    final BCryptPasswordEncoder enc = new BCryptPasswordEncoder(4);
    final UserRepository repo = mock(UserRepository.class);
    final NamedParameterJdbcTemplate jdbc = mock(NamedParameterJdbcTemplate.class);
    final MyPageService s = new MyPageService(repo, enc, jdbc);
    final User u = new User();

    MyPageServiceTest() {
        u.setId(7L); u.setEmail("farm@test.kr"); u.setName("김농부"); u.setPhone("010-1111-2222"); u.setRegionId(9);
        u.setPasswordHash(enc.encode("farm1234"));
        when(repo.findById(7L)).thenReturn(Optional.of(u));
        when(repo.saveAndFlush(any(User.class))).thenAnswer(i -> i.getArgument(0));
    }

    @Test
    void profile_update_and_nickname_rules() {
        User r = s.updateProfile(7L, new ProfileRequest(" 이농부 ", null, "010-3333-4444", "전남", " 해남농장 "));
        assertThat(r.getName()).isEqualTo("이농부");
        assertThat(r.getRegionId()).isEqualTo(14);
        assertThat(r.getFarmName()).isEqualTo("해남농장");
        when(repo.existsByNameIgnoreCase("박농부")).thenReturn(true);
        assertThatThrownBy(() -> s.updateProfile(7L, new ProfileRequest("박농부", null, "010-3333-4444", "전남", ""))).hasMessageContaining("닉네임");
        assertThatThrownBy(() -> s.updateProfile(7L, new ProfileRequest("이농부", null, "010-3333-4444", "화성", ""))).hasMessageContaining("지역");
        // 자기 닉네임 그대로(대소문자만 다름)는 중복 아님
        when(repo.existsByNameIgnoreCase("이농부")).thenReturn(true);
        assertThat(s.updateProfile(7L, new ProfileRequest("이농부", null, "010-3333-4444", "전남", "")).getFarmName()).isNull();
    }

    @Test
    void password_change() {
        assertThatThrownBy(() -> s.changePassword(7L, new PasswordRequest("wrong123", "newpass99"))).isInstanceOf(ApiException.class).hasMessageContaining("지금 비밀번호");
        assertThatThrownBy(() -> s.changePassword(7L, new PasswordRequest("farm1234", "farm1234"))).hasMessageContaining("같아요");
        s.changePassword(7L, new PasswordRequest("farm1234", "newpass99"));
        assertThat(enc.matches("newpass99", u.getPasswordHash())).isTrue();
    }

    @Test
    void favorites_input_checks() {
        assertThatThrownBy(() -> s.setFavorites(7L, List.of("Onion;drop"))).hasMessageContaining("품목 코드");
        when(jdbc.queryForList(startsWith("SELECT item_code FROM item"), anyMap(), eq(String.class))).thenReturn(List.of("onion"));
        assertThatThrownBy(() -> s.setFavorites(7L, List.of("onion", "nothing"))).hasMessageContaining("없는 품목");
        verify(jdbc, never()).update(startsWith("DELETE"), anyMap());
    }
}
