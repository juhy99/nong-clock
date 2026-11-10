package com.farm.backend.service;

import org.springframework.stereotype.Component;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 비밀번호 무차별 대입 막기 (11-10): 같은 이메일로 10분 안에 5번 틀리면 5분 동안 로그인 금지.
 * 서버 메모리에만 기억 (서버를 다시 켜면 초기화, 서버 1대 기준).
 * 한계: 남의 이메일로 일부러 5번 틀려 5분 잠그는 것은 막지 못함 (작은 서비스라 감수)
 */
@Component
public class LoginAttemptService {
    static final int MAX_FAILS = 5;
    static final Duration WINDOW = Duration.ofMinutes(10);
    static final Duration LOCK = Duration.ofMinutes(5);

    private record Entry(int fails, Instant first, Instant lockedUntil) {
    }

    private final Map<String, Entry> map = new ConcurrentHashMap<>();
    private final Clock clock;

    public LoginAttemptService() {
        this(Clock.systemUTC());
    }

    LoginAttemptService(Clock clock) {
        this.clock = clock;
    }

    /** 잠겨 있으면 남은 초, 아니면 0 */
    public long lockedSeconds(String key) {
        Entry e = map.get(key);
        if (e == null || e.lockedUntil() == null) return 0;
        long s = Duration.between(clock.instant(), e.lockedUntil()).toSeconds();
        if (s <= 0) {
            map.remove(key);
            return 0;
        }
        return s;
    }

    public void fail(String key) {
        Instant now = clock.instant();
        map.compute(key, (k, e) -> {
            if (e == null || e.first().plus(WINDOW).isBefore(now) || (e.lockedUntil() != null && !e.lockedUntil().isAfter(now)))
                e = new Entry(0, now, null);
            int n = e.fails() + 1;
            return new Entry(n, e.first(), n >= MAX_FAILS ? now.plus(LOCK) : null);
        });
        if (map.size() > 10_000) cleanup(now);
    }

    public void success(String key) {
        map.remove(key);
    }

    private void cleanup(Instant now) {
        map.entrySet().removeIf(x -> x.getValue().first().plus(WINDOW).isBefore(now)
                && (x.getValue().lockedUntil() == null || x.getValue().lockedUntil().isBefore(now)));
    }
}
