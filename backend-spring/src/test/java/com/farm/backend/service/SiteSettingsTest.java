package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.RowCallbackHandler;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.core.namedparam.SqlParameterSource;

import java.sql.ResultSet;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/** 11-17 사이트 설정: 아는 키만 · 길이 · 금칙어는 바깥에 안 나감 · 띄어쓰기를 끼워도 금칙어를 찾음 */
class SiteSettingsTest {
    private final Map<String, String> db = new HashMap<>();
    private NamedParameterJdbcTemplate jdbc;
    private SiteSettings s;

    @SuppressWarnings("unchecked")
    @BeforeEach
    void setUp() {
        jdbc = mock(NamedParameterJdbcTemplate.class);
        doAnswer(i -> {
            RowCallbackHandler h = i.getArgument(2);
            for (Map.Entry<String, String> e : db.entrySet()) {
                ResultSet rs = mock(ResultSet.class);
                when(rs.getString("key")).thenReturn(e.getKey());
                when(rs.getString("value")).thenReturn(e.getValue());
                h.processRow(rs);
            }
            return null;
        }).when(jdbc).query(anyString(), any(SqlParameterSource.class), any(RowCallbackHandler.class));
        when(jdbc.update(anyString(), anyMap())).thenAnswer(i -> {
            Map<String, Object> p = i.getArgument(1);
            db.put((String) p.get("k"), (String) p.get("v"));
            return 1;
        });
        s = new SiteSettings(jdbc);
    }

    @Test
    void save_validates_and_public_view_hides_banned_words() {
        assertThatThrownBy(() -> s.save(Map.of("admin_password", "x"))).isInstanceOf(ApiException.class).hasMessageContaining("모르는 설정");
        assertThatThrownBy(() -> s.save(Map.of("notice_text", "가".repeat(201)))).hasMessageContaining("200자");
        assertThatThrownBy(() -> s.save(Map.of("notice_on", "yes"))).hasMessageContaining("true 또는 false");
        assertThatThrownBy(() -> s.save(Map.of("contact_email", "not-mail"))).hasMessageContaining("이메일");
        s.save(Map.of("notice_on", "true", "notice_text", " 11/20 새벽 점검 ", "team_text", "홍길동 | 백엔드\n\n김농부|예측 모델", "banned_words", "도박, 대출문의"));
        Map<String, Object> v = s.publicView();
        assertThat(v.get("notice")).isEqualTo("11/20 새벽 점검");
        assertThat(v.get("maintenance")).isEqualTo("");
        assertThat(v.get("team")).isEqualTo(List.of(Map.of("name", "홍길동", "role", "백엔드"), Map.of("name", "김농부", "role", "예측 모델")));
        assertThat(v.toString()).doesNotContain("도박");
        s.save(Map.of("notice_on", "false"));
        assertThat(s.publicView().get("notice")).isEqualTo("");
    }

    @Test
    void banned_words_found_even_with_spaces_and_case() {
        s.checkWords("아무 금칙어도 없을 때는 통과");
        s.save(Map.of("banned_words", "대출문의\nCasino, 가"));   // 한 글자는 무시
        s.checkWords("가격이 올랐어요", null);
        assertThatThrownBy(() -> s.checkWords("제목", "대 출 문 의 주세요")).isInstanceOf(ApiException.class).hasMessageContaining("쓸 수 없는 낱말");
        assertThatThrownBy(() -> s.checkWords("CASINO 홍보")).hasMessageContaining("쓸 수 없는 낱말");
    }
}
