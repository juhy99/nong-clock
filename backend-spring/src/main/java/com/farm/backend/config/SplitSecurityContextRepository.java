package com.farm.backend.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpSession;
import org.springframework.security.core.context.DeferredSecurityContext;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.context.HttpRequestResponseHolder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;

/**
 * 회원 로그인과 관리자 로그인을 같은 브라우저에서 따로 유지 (11-14).
 * 브라우저 쿠키(JSESSIONID)·서버 세션은 하나지만, 로그인 정보를 세션 안 두 칸에 나눠 둔다:
 *   /api/admin/** 요청 → ADMIN_KEY 칸 (관리자, admin 표)   ·   나머지 → MEMBER_KEY 칸 (회원, users 표)
 * 그래서 관리자로 로그인해도 회원 로그인이 안 풀리고, 반대도 마찬가지. 로그아웃도 자기 칸만 지운다.
 */
public class SplitSecurityContextRepository implements SecurityContextRepository {
    public static final String MEMBER_KEY = HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY;
    public static final String ADMIN_KEY = "NONGCLOCK_ADMIN_SECURITY_CONTEXT";

    private final HttpSessionSecurityContextRepository member = new HttpSessionSecurityContextRepository();
    private final HttpSessionSecurityContextRepository admin = new HttpSessionSecurityContextRepository();

    public SplitSecurityContextRepository() {
        admin.setSpringSecurityContextKey(ADMIN_KEY);
    }

    static boolean isAdminPath(HttpServletRequest request) {
        String uri = request.getRequestURI();
        return uri != null && (uri.equals("/api/admin") || uri.startsWith("/api/admin/"));
    }

    private HttpSessionSecurityContextRepository pick(HttpServletRequest request) {
        return isAdminPath(request) ? admin : member;
    }

    @Override
    @SuppressWarnings("deprecation")
    public SecurityContext loadContext(HttpRequestResponseHolder holder) {
        return pick(holder.getRequest()).loadContext(holder);
    }

    @Override
    public DeferredSecurityContext loadDeferredContext(HttpServletRequest request) {
        return pick(request).loadDeferredContext(request);
    }

    @Override
    public void saveContext(SecurityContext context, HttpServletRequest request, HttpServletResponse response) {
        pick(request).saveContext(context, request, response);
    }

    @Override
    public boolean containsContext(HttpServletRequest request) {
        return pick(request).containsContext(request);
    }

    /**
     * 로그인: 세션 번호를 새로 받고(세션 고정 공격 막기 — 다른 칸의 로그인은 그대로 옮겨짐) 이 칸에 로그인 정보를 저장
     */
    public void login(SecurityContext context, HttpServletRequest request, HttpServletResponse response) {
        if (request.getSession(false) != null) request.changeSessionId();
        else request.getSession(true);
        SecurityContextHolder.setContext(context);
        saveContext(context, request, response);
    }

    /** 로그아웃: 이 칸(회원 또는 관리자)만 지움. 다른 쪽 로그인은 그대로 */
    public static void logout(HttpServletRequest request, String key) {
        HttpSession session = request.getSession(false);
        if (session != null) session.removeAttribute(key);
        SecurityContextHolder.clearContext();
    }
}
