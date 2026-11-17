package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.net.ConnectException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class UpdaterServiceTest {
    private final List<ClientRequest> seen = new ArrayList<>();

    private UpdaterService service(String token, ExchangeFunction fn) {
        return new UpdaterService(WebClient.builder().exchangeFunction(req -> {
            seen.add(req);
            return fn.exchange(req);
        }), "http://price-updater:8090", token);
    }

    private static ExchangeFunction json(int status, String body) {
        return req -> Mono.just(ClientResponse.create(HttpStatus.valueOf(status)).header("Content-Type", "application/json").body(body).build());
    }

    private static ApiException fails(Runnable r) {
        return assertThrows(ApiException.class, r::run);
    }

    @Test
    void sendsTokenHeader() {
        UpdaterService s = service(" secret-token ", json(200, "{\"forecast_base\":\"2026-11-14\",\"running\":null}"));
        Map<String, Object> st = s.status();
        assertEquals("2026-11-14", st.get("forecast_base"));
        assertEquals("secret-token", seen.get(0).headers().getFirst("X-Updater-Token"));
        assertEquals("/status", seen.get(0).url().getPath());
        assertFalse(st.toString().contains("secret-token"));
    }

    @Test
    void runPostsToJobPath() {
        UpdaterService s = service("t", json(202, "{\"job\":\"daily\",\"started_at\":\"2026-11-17T10:00:00\"}"));
        assertEquals("daily", s.run("daily").get("job"));
        assertEquals("POST", seen.get(0).method().name());
        assertEquals("/run/daily", seen.get(0).url().getPath());
    }

    @Test
    void busyBecomes409WithMessage() {
        ApiException e = fails(() -> service("t", json(409, "{\"message\":\"이미 갱신 중이에요 (daily · 자료 받기)\"}")).run("monthly"));
        assertEquals(HttpStatus.CONFLICT, e.getStatus());
        assertEquals("이미 갱신 중이에요 (daily · 자료 받기)", e.getMessage());
    }

    @Test
    void connectionRefusedBecomes503() {
        ApiException e = fails(() -> service("t", req -> Mono.error(new ConnectException("Connection refused"))).status());
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, e.getStatus());
        assertTrue(e.getMessage().contains("갱신 서비스가 꺼져 있어요"));
        assertFalse(e.getMessage().contains("Connection refused"));
    }

    @Test
    void updater5xxOrOddBodyBecomes503() {
        assertEquals(UpdaterService.DOWN, fails(() -> service("t", json(500, "<html>boom</html>")).status()).getMessage());
        assertEquals(UpdaterService.DOWN, fails(() -> service("t", json(404, "{\"message\":\"없는 주소예요\"}")).status()).getMessage());
    }

    @Test
    void tokenMismatchIs503NotLogout() {   // 401 을 그대로 보내면 관리자 화면이 로그아웃으로 착각함
        ApiException e = fails(() -> service("t", json(401, "{\"message\":\"허용되지 않은 요청이에요\"}")).status());
        assertEquals(HttpStatus.SERVICE_UNAVAILABLE, e.getStatus());
        assertEquals(UpdaterService.BAD_TOKEN, e.getMessage());
        assertEquals(UpdaterService.NO_TOKEN, fails(() -> service("t", json(503, "{\"message\":\"UPDATER_TOKEN 이 설정되지 않았어요 (.env)\"}")).status()).getMessage());
    }

    @Test
    void emptyTokenIs503WithoutCalling() {
        for (String tok : new String[]{"", "   ", null}) {
            ApiException e = fails(() -> service(tok, json(200, "{}")).run("daily"));
            assertEquals(HttpStatus.SERVICE_UNAVAILABLE, e.getStatus());
            assertTrue(e.getMessage().contains("UPDATER_TOKEN"));
        }
        assertTrue(seen.isEmpty());
    }

    @Test
    void unknownJobIs400() {
        for (String job : new String[]{"weekly", "", "../status", null})
            assertEquals(HttpStatus.BAD_REQUEST, fails(() -> service("t", json(202, "{}")).run(job)).getStatus());
        assertTrue(seen.isEmpty());
    }

    @Test
    void wolboChecksNameAndSendsBasename() {
        byte[] pdf = "%PDF-1.7".getBytes();
        UpdaterService s = service("t", json(201, "{\"saved\":\"VC202611.pdf\"}"));
        assertEquals("VC202611.pdf", s.uploadWolbo("C:\\Users\\M\\VC202611.pdf", pdf).get("saved"));
        assertEquals("/wolbo", seen.get(0).url().getPath());
        assertEquals("name=VC202611.pdf", seen.get(0).url().getQuery());
        seen.clear();
        for (String name : new String[]{"abc.pdf", "VC202611.txt", "", null})
            assertEquals(HttpStatus.BAD_REQUEST, fails(() -> s.uploadWolbo(name, pdf)).getStatus());
        assertEquals(HttpStatus.BAD_REQUEST, fails(() -> s.uploadWolbo("VC202611.pdf", new byte[0])).getStatus());
        assertTrue(seen.isEmpty());
        ApiException e = fails(() -> service("t", json(400, "{\"message\":\"PDF 파일이 아니에요 (내용이 PDF 형식이 아님)\"}")).uploadWolbo("VC202611.pdf", "hello".getBytes()));
        assertEquals("PDF 파일이 아니에요 (내용이 PDF 형식이 아님)", e.getMessage());
    }
}
