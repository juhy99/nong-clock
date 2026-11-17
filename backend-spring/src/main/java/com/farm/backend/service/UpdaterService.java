package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * 갱신 서비스(price-updater 컨테이너, collector/updater)에 관리자 요청을 전달 (11-17).
 * 갱신 서비스는 도커 내부망에만 있고 X-Updater-Token 이 맞아야 받는다 — 토큰은 여기(서버)에만 있고 화면에는 안 나감.
 *   갱신 서비스의 400·409·413 → 같은 코드 + 그쪽 문장 그대로 ("이미 갱신 중이에요 …", "PDF 파일이 아니에요 …")
 *   꺼져 있음·연결 실패·그 밖의 오류 → 503 "갱신 서비스가 꺼져 있어요" (관리자 화면은 이 문장만 보여 주고 나머지는 정상)
 */
@Service
public class UpdaterService {
    static final String DOWN = "갱신 서비스가 꺼져 있어요 (docker compose up -d price-updater)";
    static final String NO_TOKEN = "UPDATER_TOKEN 이 설정되지 않았어요 (.env 에 넣고 backend · price-updater 를 다시 켜 주세요)";
    static final String BAD_TOKEN = "갱신 서비스와 토큰이 서로 달라요 (backend · price-updater 를 같이 다시 켜 주세요)";
    private static final Set<String> JOBS = Set.of("daily", "monthly");
    private static final Set<Integer> PASS = Set.of(400, 409, 413);
    private static final Pattern WOLBO = Pattern.compile("^(VC|VS|VPO|F)\\d{6}.*\\.pdf$", Pattern.CASE_INSENSITIVE);
    private static final ParameterizedTypeReference<Map<String, Object>> MAP = new ParameterizedTypeReference<>() {};
    public static final long WOLBO_MAX = 50L * 1024 * 1024;

    private final WebClient web;
    private final String token;

    public UpdaterService(WebClient.Builder builder, @Value("${updater.url:http://localhost:8090}") String url,
                          @Value("${updater.token:}") String token) {
        this.web = builder.baseUrl(url).build();
        this.token = token == null ? "" : token.trim();
    }

    public Map<String, Object> status() {
        return call(web.get().uri("/status"), 10);
    }

    public Map<String, Object> run(String job) {
        if (job == null || !JOBS.contains(job)) throw new ApiException(HttpStatus.BAD_REQUEST, "없는 갱신 종류예요");
        return call(web.post().uri("/run/" + job), 10);
    }

    public Map<String, Object> uploadWolbo(String filename, byte[] body) {
        String name = filename == null ? "" : filename.replaceAll(".*[\\\\/]", "").trim();
        if (!WOLBO.matcher(name).matches())
            throw new ApiException(HttpStatus.BAD_REQUEST, "월보 파일 이름이 아니에요. VC·VS·VPO·F 로 시작하고 연월 6자리가 붙은 PDF 여야 해요 (예: VC202611.pdf)");
        if (body == null || body.length == 0) throw new ApiException(HttpStatus.BAD_REQUEST, "빈 파일이에요");
        if (body.length > WOLBO_MAX) throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, "파일이 너무 커요 (50MB 까지)");
        return call(web.post().uri(u -> u.path("/wolbo").queryParam("name", name).build())
                .contentType(MediaType.APPLICATION_PDF).bodyValue(body), 120);
    }

    private Map<String, Object> call(WebClient.RequestHeadersSpec<?> req, int seconds) {
        if (token.isEmpty()) throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, NO_TOKEN);
        try {
            Map<String, Object> out = req.header("X-Updater-Token", token)
                    .exchangeToMono(this::read)
                    .block(Duration.ofSeconds(seconds));
            return out == null ? Map.of() : out;
        } catch (ApiException e) {
            throw e;
        } catch (RuntimeException e) {   // 연결 거부 · 이름 못 찾음(컨테이너 없음) · 시간 초과
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, DOWN);
        }
    }

    private Mono<Map<String, Object>> read(ClientResponse res) {
        int code = res.statusCode().value();
        if (code >= 200 && code < 300) return res.bodyToMono(MAP);
        return res.bodyToMono(MAP).onErrorReturn(Map.of()).defaultIfEmpty(Map.of()).flatMap(body -> {
            Object m = body.get("message");
            if (PASS.contains(code) && m instanceof String s && !s.isBlank())
                return Mono.error(new ApiException(HttpStatus.valueOf(code), s));
            if (code == 401) return Mono.error(new ApiException(HttpStatus.SERVICE_UNAVAILABLE, BAD_TOKEN));
            if (code == 503 && m instanceof String s && s.contains("UPDATER_TOKEN"))
                return Mono.error(new ApiException(HttpStatus.SERVICE_UNAVAILABLE, NO_TOKEN));
            return Mono.error(new ApiException(HttpStatus.SERVICE_UNAVAILABLE, DOWN));
        });
    }
}
