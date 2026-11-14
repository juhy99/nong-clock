package com.farm.backend.config;

import com.farm.backend.domain.User;
import com.farm.backend.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * 관리자 지정 (11-14). 서버가 켜질 때 ADMIN_EMAILS(쉼표로 여러 개)에 적힌 이메일의 회원을 관리자(users.role = ADMIN)로 바꾼다.
 * - 그 이메일로 먼저 회원가입해 두고, 서버 .env 에 ADMIN_EMAILS=이메일 → backend 다시 켜기 → 그 계정으로 다시 로그인
 * - 목록에서 지운 이메일도 일반회원으로 되돌린다 (관리자 = 언제나 이 목록). 비어 있으면 아무것도 바꾸지 않음
 * - 아직 가입하지 않은 이메일은 건너뜀 (로그에 남김)
 */
@Component
public class AdminAccounts implements ApplicationRunner {
    private static final Logger log = LoggerFactory.getLogger(AdminAccounts.class);

    private final UserRepository users;
    private final List<String> emails;

    public AdminAccounts(UserRepository users, @Value("${admin.emails:}") String emails) {
        this.users = users;
        this.emails = parse(emails);
    }

    static List<String> parse(String s) {
        return s == null ? List.of() : Arrays.stream(s.split(",")).map(x -> x.trim().toLowerCase(Locale.ROOT)).filter(x -> !x.isEmpty()).distinct().toList();
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (emails.isEmpty()) return;
        for (User u : users.findAll()) {
            String want = emails.contains(u.getEmail()) ? User.ROLE_ADMIN : User.ROLE_MEMBER;
            if (!want.equals(u.getRole())) {
                u.setRole(want);
                users.save(u);
                log.info("관리자 지정: {} → {}", u.getEmail(), want);
            }
        }
        emails.stream().filter(e -> users.findByEmail(e).isEmpty()).forEach(e -> log.warn("ADMIN_EMAILS 의 {} 은(는) 아직 가입하지 않은 이메일이에요", e));
    }
}
