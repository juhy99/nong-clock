package com.farm.backend.controller;

import com.farm.backend.config.ApiException;
import com.farm.backend.config.LoginUser;
import com.farm.backend.domain.User;
import com.farm.backend.dto.FavoritesRequest;
import com.farm.backend.dto.LoginRequest;
import com.farm.backend.dto.MyCommentResponse;
import com.farm.backend.dto.PasswordRequest;
import com.farm.backend.dto.PostResponse;
import com.farm.backend.dto.ProfileRequest;
import com.farm.backend.dto.SignupRequest;
import com.farm.backend.dto.UserResponse;
import com.farm.backend.dto.WithdrawRequest;
import com.farm.backend.service.MyPageService;
import com.farm.backend.service.UserService;
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
 * 회원 API — docs/06_api_spec.md 2장 (11-10 보안 고침: 주소를 명세서대로 /api/auth/... 로, 세션 로그인)
 *   POST /api/auth/signup   가입 (성공하면 바로 로그인 상태)      201 · 409 중복 · 422 입력 오류
 *   POST /api/auth/login    로그인                               200 · 401 틀림
 *   POST /api/auth/logout   로그아웃                             204
 *   GET  /api/auth/check?email= | ?nickname=   중복 확인 {"taken": true}
 *   GET  /api/me            지금 로그인한 회원 (새로고침 때 화면이 확인)  200 · 401
 *   DELETE /api/me {"password"}  회원 탈퇴: 회원·쓴 글을 DB 에서 지우고 로그아웃   204 · 403 비밀번호 틀림
 *   ── 마이페이지 (11-16, 명세서 2-6 ~ 2-8) ──
 *   PATCH /api/me {nickname, phone, region, farm_name}   내 정보 수정 → 회원 정보   200 · 409 닉네임 중복 · 422 입력 오류
 *   PUT  /api/me/password {current, next}   비밀번호 변경   204 · 403 지금 비밀번호 틀림 · 422 규칙·같은 비밀번호
 *   GET  /api/me/posts · /api/me/comments   내가 쓴 글·댓글 (최근 100개)
 *   GET  /api/me/favorites · PUT /api/me/favorites {items: [품목 코드]}   관심 품목 (DB user_favorite)
 * 응답의 회원 정보에는 비밀번호가 없다 (UserResponse).
 */
@RestController
@RequestMapping("/api")
public class UserController {

    private final UserService userService;
    private final MyPageService myPage;
    private final SplitSecurityContextRepository contextRepository;

    public UserController(UserService userService, MyPageService myPage, SplitSecurityContextRepository contextRepository) {
        this.userService = userService;
        this.myPage = myPage;
        this.contextRepository = contextRepository;
    }

    @PostMapping("/auth/signup")
    public ResponseEntity<UserResponse> signup(@Valid @RequestBody SignupRequest body, HttpServletRequest request, HttpServletResponse response) {
        User user = userService.signup(body);
        startSession(user, request, response);
        return ResponseEntity.status(HttpStatus.CREATED).body(UserService.toResponse(user));
    }

    @PostMapping("/auth/login")
    public UserResponse login(@Valid @RequestBody LoginRequest body, HttpServletRequest request, HttpServletResponse response) {
        User user = userService.login(body.email(), body.password());
        startSession(user, request, response);
        return UserService.toResponse(user, myPage.favorites(user.getId()));
    }

    @PostMapping("/auth/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        endSession(request);
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/auth/check")
    public Map<String, Boolean> check(@RequestParam(required = false) String email, @RequestParam(required = false) String nickname) {
        if (email != null && !email.isBlank()) return Map.of("taken", userService.isEmailTaken(email));
        if (nickname != null && !nickname.isBlank()) return Map.of("taken", userService.isNicknameTaken(nickname));
        throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "email 또는 nickname 을 주세요");
    }

    /** 로그인 필수 (SecurityConfig). 다른 기기에서 탈퇴해 지워진 회원의 남은 세션은 여기서 끊음 */
    @GetMapping("/me")
    public UserResponse me(@AuthenticationPrincipal LoginUser me, HttpServletRequest request) {
        User user = userService.findUser(me == null ? null : me.id());
        if (user == null) {
            endSession(request);
            throw new ApiException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다");
        }
        return UserService.toResponse(user, myPage.favorites(user.getId()));
    }

    /** 내 정보 수정 (11-16). 이메일은 못 바꿈 */
    @PatchMapping("/me")
    public UserResponse updateMe(@AuthenticationPrincipal LoginUser me, @Valid @RequestBody ProfileRequest body) {
        User user = myPage.updateProfile(me.id(), body);
        return UserService.toResponse(user, myPage.favorites(user.getId()));
    }

    /** 비밀번호 변경 (11-16). 바꾼 뒤 세션 번호를 새로 받음 (예전 세션 번호를 누가 알아도 못 쓰게) */
    @PutMapping("/me/password")
    public ResponseEntity<Void> changePassword(@AuthenticationPrincipal LoginUser me, @Valid @RequestBody PasswordRequest body, HttpServletRequest request) {
        myPage.changePassword(me.id(), body);
        if (request.getSession(false) != null) request.changeSessionId();
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/me/posts")
    public List<PostResponse> myPosts(@AuthenticationPrincipal LoginUser me) {
        return myPage.myPosts(me.id());
    }

    @GetMapping("/me/comments")
    public List<MyCommentResponse> myComments(@AuthenticationPrincipal LoginUser me) {
        return myPage.myComments(me.id());
    }

    @GetMapping("/me/favorites")
    public List<String> favorites(@AuthenticationPrincipal LoginUser me) {
        return myPage.favorites(me.id());
    }

    @PutMapping("/me/favorites")
    public List<String> setFavorites(@AuthenticationPrincipal LoginUser me, @RequestBody FavoritesRequest body) {
        return myPage.setFavorites(me.id(), body == null ? null : body.items());
    }

    /** 회원 탈퇴 (로그인 필수). 비밀번호 확인 → 쓴 글·회원 삭제 → 세션 끊기. 화면은 로그인 화면으로 이동 */
    @DeleteMapping("/me")
    public ResponseEntity<Void> withdraw(@AuthenticationPrincipal LoginUser me, @RequestBody WithdrawRequest body, HttpServletRequest request) {
        userService.withdraw(me.id(), body.password());
        endSession(request);
        return ResponseEntity.noContent().build();
    }

    /**
     * 로그인 상태 만들기: 예전 세션을 버리고 새 세션 번호를 받은 뒤(세션 고정 공격 막기) 로그인 정보를 세션에 저장.
     * 권한은 지금 모두 ROLE_MEMBER (관리자 열이 DB 에 생기면 ROLE_ADMIN 추가)
     */
    private void startSession(User user, HttpServletRequest request, HttpServletResponse response) {
        UsernamePasswordAuthenticationToken auth = UsernamePasswordAuthenticationToken.authenticated(
                new LoginUser(user.getId(), user.getEmail()), null, List.of(new SimpleGrantedAuthority("ROLE_MEMBER")));
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(auth);
        contextRepository.login(context, request, response); // 세션 번호를 새로 받고 회원 칸에 저장 — 관리자 로그인은 그대로 (11-14)
    }

    /** 회원 로그아웃: 회원 칸만 지움 (같은 브라우저의 관리자 로그인은 그대로, 11-14) */
    private void endSession(HttpServletRequest request) {
        SplitSecurityContextRepository.logout(request, SplitSecurityContextRepository.MEMBER_KEY);
    }
}
