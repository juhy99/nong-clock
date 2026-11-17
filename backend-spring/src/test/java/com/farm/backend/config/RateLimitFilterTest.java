package com.farm.backend.config;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class RateLimitFilterTest {
    @Test
    void refreshWritesAreLimitedReadsAreNot() {
        assertSame(RateLimitFilter.WRITE, RateLimitFilter.ruleOf("POST", "/api/admin/refresh/daily"));
        assertSame(RateLimitFilter.WRITE, RateLimitFilter.ruleOf("POST", "/api/admin/refresh/wolbo"));
        assertNull(RateLimitFilter.ruleOf("GET", "/api/admin/refresh"));   // 5초마다 상태 확인은 한도 없음
    }

    @Test
    void existingRulesUnchanged() {
        assertSame(RateLimitFilter.AUTH, RateLimitFilter.ruleOf("POST", "/api/auth/login"));
        assertSame(RateLimitFilter.WRITE, RateLimitFilter.ruleOf("POST", "/api/posts"));
        assertNull(RateLimitFilter.ruleOf("GET", "/api/posts"));
        assertNull(RateLimitFilter.ruleOf("PUT", "/api/admin/site"));
    }
}
