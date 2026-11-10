package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.User;
import com.farm.backend.dto.SignupRequest;
import com.farm.backend.dto.UserResponse;
import com.farm.backend.repository.UserRepository;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Locale;

/**
 * 회원가입·로그인 (11-10 보안 고침).
 * - 비밀번호: BCrypt 로 암호화해 저장, 확인도 BCrypt (예전: 글자 그대로 저장·비교)
 * - 로그인 실패 문장은 하나로 ("이메일 또는 비밀번호가 맞지 않습니다") → 어떤 이메일이 가입됐는지 알 수 없게
 * - 정지·탈퇴 회원은 비밀번호가 맞아도 로그인 거부
 */
@Service
@Transactional(readOnly = true)
public class UserService {

    /** 시·도 이름 → region_id (수집기 ref/region.csv · DB region 표와 같은 번호 1~17) */
    static final List<String> REGIONS = List.of(
            "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주");

    static final String LOGIN_FAIL = "이메일 또는 비밀번호가 맞지 않습니다";

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    /** 없는 이메일로 로그인할 때도 비밀번호 확인과 같은 시간이 걸리게 하는 가짜 해시 (응답 시간으로 가입 여부를 알 수 없게) */
    private final String dummyHash;

    public UserService(UserRepository userRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.dummyHash = passwordEncoder.encode("dummy-password-for-timing-1234");
    }

    static Integer regionId(String name) {
        if (name == null || name.isBlank()) return null;
        int i = REGIONS.indexOf(name.trim());
        return i < 0 ? null : i + 1;
    }

    static String regionName(Integer id) {
        return id == null || id < 1 || id > REGIONS.size() ? null : REGIONS.get(id - 1);
    }

    static String normEmail(String email) {
        return email == null ? "" : email.trim().toLowerCase(Locale.ROOT);
    }

    /** 닉네임: 앞뒤 공백 빼고 2~20자. 틀리면 422 */
    static String normNickname(String nickname, String name) {
        String v = nickname != null && !nickname.isBlank() ? nickname : name;
        v = v == null ? "" : v.trim();
        if (v.length() < 2 || v.length() > 20) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "닉네임은 2~20자로 입력하세요");
        return v;
    }

    /** [중복 확인] 버튼: GET /api/auth/check?email= 또는 ?nickname= */
    public boolean isEmailTaken(String email) {
        return userRepository.existsByEmail(normEmail(email));
    }

    public boolean isNicknameTaken(String nickname) {
        return nickname != null && userRepository.existsByNameIgnoreCase(nickname.trim());
    }

    @Transactional
    public User signup(SignupRequest r) {
        String email = normEmail(r.email());
        String nickname = normNickname(r.nickname(), r.name());
        Integer region = regionId(r.region());
        if (region == null) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "지역을 선택하세요");
        if (userRepository.existsByEmail(email)) throw new ApiException(HttpStatus.CONFLICT, "이미 가입된 이메일입니다");
        if (userRepository.existsByNameIgnoreCase(nickname)) throw new ApiException(HttpStatus.CONFLICT, "이미 사용 중인 닉네임이에요");

        User user = new User();
        user.setEmail(email);
        user.setPasswordHash(passwordEncoder.encode(r.password()));
        user.setName(nickname);
        user.setPhone(r.phone().trim());
        user.setRegionId(region);
        user.setFarmName(r.farmName() == null || r.farmName().isBlank() ? null : r.farmName().trim());
        user.setMarketingAgree(Boolean.TRUE.equals(r.marketing()));
        user.setStatus("ACTIVE");
        try {
            return userRepository.saveAndFlush(user);
        } catch (DataIntegrityViolationException e) { // 같은 이메일로 동시에 두 번 가입하면 DB UNIQUE 가 막음
            throw new ApiException(HttpStatus.CONFLICT, "이미 가입된 이메일입니다");
        }
    }

    public User login(String rawEmail, String password) {
        String email = normEmail(rawEmail);
        User user = userRepository.findByEmail(email).orElse(null);
        boolean ok = passwordEncoder.matches(password, user == null ? dummyHash : user.getPasswordHash()) && user != null;
        if (!ok) throw new ApiException(HttpStatus.UNAUTHORIZED, LOGIN_FAIL);
        if ("SUSPENDED".equals(user.getStatus())) throw new ApiException(HttpStatus.FORBIDDEN, "이용이 정지된 계정입니다. 고객센터에 문의하세요");
        if ("WITHDRAWN".equals(user.getStatus())) throw new ApiException(HttpStatus.FORBIDDEN, "탈퇴한 계정입니다");
        return user;
    }

    /** 세션의 회원 번호로 지금 정보 읽기 (GET /api/me). 없거나 정상 상태가 아니면 null → 컨트롤러가 세션을 끊음 */
    public User activeUser(Long id) {
        if (id == null) return null;
        return userRepository.findById(id).filter(u -> "ACTIVE".equals(u.getStatus())).orElse(null);
    }

    public static UserResponse toResponse(User u) {
        return new UserResponse(u.getId(), u.getEmail(), u.getName(), u.getName(), u.getPhone(), regionName(u.getRegionId()),
                u.getFarmName() == null ? "" : u.getFarmName(), "MEMBER", u.getStatus());
    }
}
