package com.farm.backend.controller;

import com.farm.backend.domain.User;
import com.farm.backend.service.UserService;
import lombok.Getter;
import lombok.RequiredArgsConstructor;
import lombok.Setter;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
// 만약 다른 API처럼 기본 주소를 맞추고 싶다면 아래처럼 유지하되,
// 프론트엔드 요청 주소를 일치시켜야 합니다. 여기서는 /register 단독 사용을 위해 클래스 레벨 RequestMapping을 수정합니다.
@RequiredArgsConstructor
@CrossOrigin(origins = "http://localhost:5173")
public class UserController {

    private final UserService userService;

    // 💡 프론트엔드에서 보내는 데이터 필드명과 일치시키기
    @Getter @Setter
    public static class RegisterRequest {
        private String email;
        private String password;
        private String name;
        private String phone;
        private String region;
        private String farmName; // 프론트의 farm_name이 자바 관례상 보통 camelCase인 farmName으로 매핑됨
        private boolean marketing;
    }

    @Getter @Setter
    public static class LoginRequest {
        private String email;
        private String password;
    }

    /**
     * 💡 회원가입 API 주소를 프론트엔드와 맞춤 (POST /register)
     */
    @PostMapping("/register")
    public ResponseEntity<?> register(@RequestBody RegisterRequest request) {
        try {
            // 💡 6개의 데이터를 모두 서비스로 넘기도록 수정
            userService.register(
                    request.getEmail(),
                    request.getPassword(),
                    request.getName(),
                    request.getPhone(),
                    request.getRegion(),
                    request.getFarmName()
            );
            return ResponseEntity.ok("회원가입이 완료되었습니다.");
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        try {
            User user = userService.login(request.getEmail(), request.getPassword());
            // 프론트엔드 세션 저장을 위해 user 객체(또는 필요한 정보)를 그대로 리턴해주는 것이 좋습니다.
            return ResponseEntity.ok(user);
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }
}