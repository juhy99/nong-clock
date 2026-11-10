package com.farm.backend.config;

import jakarta.servlet.http.HttpServletResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.io.IOException;
import java.util.List;

import static org.springframework.security.web.util.matcher.AntPathRequestMatcher.antMatcher;

/**
 * 로그인 보안 설정 (2026-11-10).
 * - 로그인 상태는 서버 세션에 둔다. 브라우저에는 세션 번호 쿠키(JSESSIONID)만 간다.
 *   쿠키는 HttpOnly(자바스크립트로 못 읽음) · SameSite=Lax (application.yml server.servlet.session.cookie)
 * - 비밀번호는 BCrypt 로 암호화해 저장한다 (같은 비밀번호도 저장값이 매번 다름, 되돌릴 수 없음)
 * - 로그인이 필요한 주소: /api/me/** (내 정보), 게시판·댓글 쓰기·고치기·지우기 (POST·PUT·PATCH·DELETE /api/posts/**, DELETE /api/comments/**).
 *   관리자 주소: /api/admin/** (관리자 지정 열이 생기면 사용)
 *   나머지 주소(시세·게시판 읽기 등)는 지금처럼 누구나. 경매 등 새 API 는 만들 때 여기에 한 줄씩 추가
 * - CSRF 토큰은 끔: 화면과 API 가 같은 주소(nginx·vite 프록시)라 다른 사이트에서는 SameSite=Lax 때문에 쿠키가 안 붙고,
 *   API 는 JSON 만 받아 다른 사이트의 폼 전송으로는 호출할 수 없다. 화면과 API 를 다른 도메인으로 나누면 다시 켜야 함
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    /** 로그인 성공 때 컨트롤러가 직접 세션에 로그인 정보를 저장할 때 씀 (UserController) */
    @Bean
    public SecurityContextRepository securityContextRepository() {
        return new HttpSessionSecurityContextRepository();
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http, SecurityContextRepository contextRepository) throws Exception {
        http
                .csrf(AbstractHttpConfigurer::disable)
                .cors(Customizer.withDefaults())
                .formLogin(AbstractHttpConfigurer::disable)   // 스프링 기본 로그인 화면 대신 /api/auth/login (JSON)
                .httpBasic(AbstractHttpConfigurer::disable)
                .logout(AbstractHttpConfigurer::disable)      // 로그아웃은 /api/auth/logout (UserController)
                .securityContext(c -> c.securityContextRepository(contextRepository))
                .sessionManagement(s -> s.sessionFixation(f -> f.changeSessionId()))
                .exceptionHandling(e -> e
                        .authenticationEntryPoint((req, res, ex) -> json(res, 401, "로그인이 필요합니다"))
                        .accessDeniedHandler((req, res, ex) -> json(res, 403, "권한이 없습니다")))
                .authorizeHttpRequests(a -> a
                        .requestMatchers(antMatcher("/api/me"), antMatcher("/api/me/**")).authenticated()
                        .requestMatchers(antMatcher(HttpMethod.POST, "/api/posts"), antMatcher(HttpMethod.POST, "/api/posts/**"),
                                antMatcher(HttpMethod.PUT, "/api/posts/**"), antMatcher(HttpMethod.PATCH, "/api/posts/**"),
                                antMatcher(HttpMethod.DELETE, "/api/posts/**"), antMatcher(HttpMethod.DELETE, "/api/comments/**")).authenticated()
                        .requestMatchers(antMatcher("/api/admin/**")).hasRole("ADMIN")
                        .anyRequest().permitAll());
        return http.build();
    }

    /** 내 PC 개발: 화면(localhost:5173)은 보통 vite 프록시로 같은 주소처럼 부르지만, 직접 8080 을 부를 때를 위해 허용 */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration c = new CorsConfiguration();
        c.setAllowedOrigins(List.of("http://localhost:5173"));
        c.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        c.setAllowedHeaders(List.of("Content-Type"));
        c.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", c);
        return source;
    }

    private static void json(HttpServletResponse res, int status, String message) throws IOException {
        res.setStatus(status);
        res.setContentType("application/json;charset=UTF-8");
        res.getWriter().write("{\"message\":\"" + message + "\"}");
    }
}
