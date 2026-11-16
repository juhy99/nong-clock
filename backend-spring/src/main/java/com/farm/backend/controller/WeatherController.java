package com.farm.backend.controller;

import com.farm.backend.service.WeatherService;

import org.springframework.web.bind.annotation.*;

import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.server.ResponseStatusException;

/**
 * 지금 날씨 API (11-14) — docs/06_api_spec.md 2-7. 화면: 홈 › 우리 지역 농업 날씨의 "지금" 줄 (frontend/src/api/market.js getRegionalWeather)
 * 기상청 초단기실황·단기예보·기상특보를 시·도 17곳으로 (10분 캐시). 키가 없으면 503 → 화면은 지난 날씨만 보여 줌
 */
@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:5173")
public class WeatherController {
    private static final Logger log = LoggerFactory.getLogger(WeatherController.class);
    private final WeatherService weather;

    public WeatherController(WeatherService weather) {
        this.weather = weather;
    }

    @GetMapping("/weather/regions")
    public Map<String, Object> regions() {
        return weather.regions();
    }

    /** 11-16: 실패 이유를 {"message"} 로 돌려주고 로그에도 남김 — 예전엔 502 만 나가고 이유가 어디에도 안 남았음 (키 값은 문장에 없음) */
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> failed(ResponseStatusException e) {
        String why = e.getReason() == null ? "날씨를 받지 못했어요" : e.getReason();
        log.warn("지금 날씨 실패 {}: {}", e.getStatusCode().value(), why);
        return ResponseEntity.status(e.getStatusCode()).body(Map.of("message", why));
    }
}
