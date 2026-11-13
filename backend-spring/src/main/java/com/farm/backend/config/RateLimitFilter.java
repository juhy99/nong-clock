package com.farm.backend.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;

/**
 * IP(접속한 컴퓨터)별 요청 수 제한 (11-13 보안). 넘으면 429 + {"message"} — 화면 ErrorPopup 이 그대로 보여 줌.
 * - 로그인·가입·중복 확인: 1분에 20번 → 비밀번호를 마구 넣어 보는 공격(무차별 대입)을 느리게 만듦.
 *   계정을 잠그지는 않는다 (11-10 결정: 로그인 실패 잠금은 뺌). 같은 IP 만 1분 기다리면 됨
 * - 글·댓글 쓰기·고치기·지우기, 탈퇴: 1분에 30번 → 도배 막기. 읽기(GET)는 제한 없음
 * 서버에서는 nginx(frontend/nginx.conf)가 앞에서 한 번 더 막는다. 이 필터는 nginx 없이 Spring 을 직접 켤 때(내 PC)도 지키려는 것.
 * 진짜 IP 는 nginx 가 넘긴 X-Forwarded-For (application.yml server.forward-headers-strategy=native 가 request.getRemoteAddr() 로 바꿔 줌).
 * 기록은 메모리에만 (Spring 을 다시 켜면 초기화). 서버를 여러 대로 늘리면 Redis 같은 공용 저장소가 필요
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {
    record Rule(String name, int limit, long windowMs) {}

    static final Rule AUTH = new Rule("auth", 20, 60_000);
    static final Rule WRITE = new Rule("write", 30, 60_000);
    private static final int MAX_KEYS = 50_000; // 이보다 많아지면 끝난 창을 지움 (메모리가 끝없이 늘지 않게)

    private final Map<String, long[]> hits = new ConcurrentHashMap<>(); // "규칙|IP" → [창 시작 시각, 횟수]
    private final LongSupplier clock;

    public RateLimitFilter() {
        this(System::currentTimeMillis);
    }

    RateLimitFilter(LongSupplier clock) {
        this.clock = clock;
    }

    static Rule ruleOf(String method, String path) {
        if (path == null) return null;
        if (path.equals("/api/auth/login") || path.equals("/api/auth/signup") || path.equals("/api/auth/check")) return AUTH;
        boolean read = method.equals("GET") || method.equals("HEAD") || method.equals("OPTIONS");
        if (!read && (path.startsWith("/api/posts") || path.startsWith("/api/comments") || path.equals("/api/me"))) return WRITE;
        return null;
    }

    /** 이번 요청이 한도 안인지 (고정 창: 창이 지나면 다시 0부터) */
    boolean allow(String ip, Rule rule) {
        long now = clock.getAsLong();
        if (hits.size() > MAX_KEYS) hits.values().removeIf(v -> now - v[0] >= 60_000);
        long[] w = hits.compute(rule.name() + "|" + ip,
                (k, v) -> v == null || now - v[0] >= rule.windowMs() ? new long[]{now, 1} : new long[]{v[0], v[1] + 1});
        return w[1] <= rule.limit();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException, IOException {
        Rule rule = ruleOf(req.getMethod(), req.getRequestURI());
        if (rule == null || allow(req.getRemoteAddr(), rule)) {
            chain.doFilter(req, res);
            return;
        }
        res.setStatus(429);
        res.setHeader("Retry-After", "60");
        res.setContentType("application/json;charset=UTF-8");
        res.getWriter().write("{\"message\":\"요청이 너무 많아요. 1분쯤 뒤에 다시 시도해 주세요\"}");
    }
}
