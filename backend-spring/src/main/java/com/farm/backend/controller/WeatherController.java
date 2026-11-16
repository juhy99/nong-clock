package com.farm.backend.controller;

import com.farm.backend.service.WeatherService;

import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 지금 날씨 API (11-14) — docs/06_api_spec.md 2-7. 화면: 홈 › 우리 지역 농업 날씨의 "지금" 줄 (frontend/src/api/market.js getRegionalWeather)
 * 기상청 초단기실황·단기예보·기상특보를 시·도 17곳으로 (10분 캐시). 키가 없으면 503 → 화면은 지난 날씨만 보여 줌
 */
@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:5173")
public class WeatherController {
    private final WeatherService weather;

    public WeatherController(WeatherService weather) {
        this.weather = weather;
    }

    @GetMapping("/weather/regions")
    public Map<String, Object> regions() {
        return weather.regions();
    }
}
