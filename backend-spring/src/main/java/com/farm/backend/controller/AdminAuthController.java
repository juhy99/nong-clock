package com.farm.backend.controller;

import com.farm.backend.config.AdminUser;
import com.farm.backend.config.ApiException;
import com.farm.backend.domain.Admin;
import com.farm.backend.dto.LoginRequest;
import com.farm.backend.service.AdminService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import com.farm.backend.config.SplitSecurityContextRepository;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 관리자 로그인 (11-14) — 관리자 사이트(/admin/) 전용. 계정은 DB 표 admin.
 *   POST /api/admin/auth/login  {"email","password"}  200 {id,email,name} · 401
 *   POST /api/admin/auth/logout                        204
 *   GET  /api/admin/me                                 200 · 401(로그인 안 함) · 403(회원으로 로그인)
 * 로그인하면 세션의 관리자 칸에 AdminUser + ROLE_ADMIN. 같은 브라우저의 회원 로그인과 따로 유지됨 (SplitSecurityContextRepository)
 */
@RestController
@RequestMapping("/api/admin")
public class AdminAuthController {
    private final AdminService adminService;
    private final SplitSecurityContextRepository contextRepository;

    public AdminAuthController(AdminService adminService, SplitSecurityContextRepository contextRepository) {
        this.adminService = adminService;
        this.contextRepository = contextRepository;
    }

    @PostMapping("/auth/login")
    public Map<String, Object> login(@Valid @RequestBody LoginRequest body, HttpServletRequest request, HttpServletResponse response) {
        Admin a = adminService.login(body.email(), body.password());
        UsernamePasswordAuthenticationToken auth = UsernamePasswordAuthenticationToken.authenticated(
                new AdminUser(a.getId(), a.getEmail(), a.getName()), null, List.of(new SimpleGrantedAuthority("ROLE_ADMIN")));
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(auth);
        contextRepository.login(context, request, response); // 관리자 칸에 저장 — 같은 브라우저의 회원 로그인은 그대로 (11-14)
        return view(a);
    }

    @PostMapping("/auth/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        SplitSecurityContextRepository.logout(request, SplitSecurityContextRepository.ADMIN_KEY); // 관리자 칸만
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/me")
    public Map<String, Object> me(@AuthenticationPrincipal AdminUser me, HttpServletRequest request) {
        Admin a = adminService.find(me == null ? null : me.id());
        if (a == null) {
            logout(request);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다");
        }
        return view(a);
    }

    private static Map<String, Object> view(Admin a) {
        return Map.of("id", a.getId(), "email", a.getEmail(), "name", a.getName());
    }
}
