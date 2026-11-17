package com.farm.backend.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.function.Supplier;

/**
 * 오류 기록 (11-17, 관리자 '오류 기록' 화면). Spring 이 내보낸 응답 중 문제만 메모리에 남김:
 *   서버 오류(5xx) · 요청 수 제한(429) · 로그인 실패(/api/auth/login · /api/admin/auth/login 의 401)
 * - 최근 300건 + 시간대별 횟수 48시간. 서버를 다시 켜면 비워짐 (DB 에 쌓지 않음 — 서버가 여러 대가 되면 공용 저장소 필요)
 * - 개인 정보: 주소(쿼리 뺌) · IP 끝자리 가림 · 요청 본문·이메일·비밀번호는 남기지 않음
 * - nginx 가 앞에서 막은 429 와 ml-api 오류는 Spring 까지 오지 않아 여기 없음 (화면에 밝힘)
 * 가장 바깥 필터라 보안·요청 제한 필터가 정한 응답 코드도 봄
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class OpsLog extends OncePerRequestFilter {
    public record Event(String at, String kind, int status, String method, String path, String ip, String note) {
    }

    static final int MAX_EVENTS = 300, HOURS = 48;
    private final Deque<Event> events = new ArrayDeque<>();
    private final Map<String, int[]> hourly = new LinkedHashMap<>();   // "yyyy-MM-ddTHH" → [5xx, 429, 로그인 실패]
    private final Supplier<LocalDateTime> clock;

    public OpsLog() {
        this(LocalDateTime::now);
    }

    OpsLog(Supplier<LocalDateTime> clock) {
        this.clock = clock;
    }

    static String kindOf(int status, String path) {
        if (status >= 500) return "server";
        if (status == 429) return "limit";
        if (status == 401 && path != null && (path.equals("/api/auth/login") || path.equals("/api/admin/auth/login"))) return "login";
        return null;
    }

    static String maskIp(String ip) {
        if (ip == null) return "";
        int dot = ip.lastIndexOf('.');
        return dot > 0 ? ip.substring(0, dot) + ".*" : ip.replaceAll(":[0-9a-fA-F]*$", ":*");
    }

    /** 응답 하나를 보고 문제면 기록. note = 오류 종류(예외 이름) 등 */
    public synchronized void record(int status, String method, String path, String ip, String note) {
        String kind = kindOf(status, path);
        if (kind == null) return;
        LocalDateTime now = clock.get();
        events.addFirst(new Event(now.truncatedTo(ChronoUnit.SECONDS).toString(), kind, status, method,
                path == null ? "" : path.length() > 120 ? path.substring(0, 120) : path, maskIp(ip), note == null ? "" : note));
        while (events.size() > MAX_EVENTS) events.removeLast();
        String hour = now.truncatedTo(ChronoUnit.HOURS).toString().substring(0, 13);
        int[] c = hourly.computeIfAbsent(hour, k -> new int[3]);
        c[kind.equals("server") ? 0 : kind.equals("limit") ? 1 : 2]++;
        String oldest = now.minusHours(HOURS).truncatedTo(ChronoUnit.HOURS).toString().substring(0, 13);
        hourly.keySet().removeIf(k -> k.compareTo(oldest) < 0);
    }

    /** 처리하지 못한 예외의 종류를 다음 기록에 붙이려고 요청에 적어 둠 (ApiExceptionHandler 가 부름) */
    public static void note(HttpServletRequest req, Throwable e) {
        if (req != null && e != null) req.setAttribute(OpsLog.class.getName(), e.getClass().getSimpleName());
    }

    public synchronized Map<String, Object> snapshot() {
        List<Map<String, Object>> hours = new ArrayList<>();
        hourly.forEach((h, c) -> hours.add(Map.of("hour", h, "server", c[0], "limit", c[1], "login", c[2])));
        int[] total = new int[3];
        hourly.values().forEach(c -> { total[0] += c[0]; total[1] += c[1]; total[2] += c[2]; });
        return Map.of("events", List.copyOf(events), "hours", hours,
                "total", Map.of("server", total[0], "limit", total[1], "login", total[2]), "since_hours", HOURS, "max_events", MAX_EVENTS);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException, IOException {
        try {
            chain.doFilter(req, res);
        } catch (ServletException | IOException | RuntimeException e) {
            record(500, req.getMethod(), req.getRequestURI(), req.getRemoteAddr(), e.getClass().getSimpleName());
            throw e;
        }
        Object note = req.getAttribute(OpsLog.class.getName());
        record(res.getStatus(), req.getMethod(), req.getRequestURI(), req.getRemoteAddr(), note == null ? null : note.toString());
    }
}
