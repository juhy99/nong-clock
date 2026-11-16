package com.farm.backend.service;

import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/** 지금 날씨 변환 시험 (11-14): 기상청 응답 모양을 손으로 만들어 넣고 결과를 본다 (실제 호출 없음) */
class WeatherServiceTest {
    private static final String NCST = """
        {"response":{"header":{"resultCode":"00","resultMsg":"NORMAL_SERVICE"},"body":{"items":{"item":[
          {"category":"T1H","obsrValue":"7.6"},{"category":"REH","obsrValue":"55"},{"category":"WSD","obsrValue":"2.1"},{"category":"PTY","obsrValue":"0"}]}}}}""";
    private static final String FCST = """
        {"response":{"header":{"resultCode":"00","resultMsg":"NORMAL_SERVICE"},"body":{"items":{"item":[
          {"category":"TMN","fcstDate":"%1$s","fcstTime":"0600","fcstValue":"-1.0"},
          {"category":"TMX","fcstDate":"%1$s","fcstTime":"1500","fcstValue":"12.0"},
          {"category":"TMP","fcstDate":"%1$s","fcstTime":"0000","fcstValue":"3"},
          {"category":"SKY","fcstDate":"%1$s","fcstTime":"0000","fcstValue":"3"},
          {"category":"POP","fcstDate":"%1$s","fcstTime":"0000","fcstValue":"20"},
          {"category":"PTY","fcstDate":"%1$s","fcstTime":"0000","fcstValue":"0"}]}}}}""";
    private static final String WARN = """
        {"response":{"header":{"resultCode":"00"},"body":{"items":{"item":[
          {"t6":"o 강풍주의보 : 제주도(제주도산지), 강원도(강원북부산지)\\no 건조주의보 : 강원도"}]}}}}""";

    private static String today() {
        return java.time.ZonedDateTime.now(java.time.ZoneId.of("Asia/Seoul")).format(WeatherService.YMD); // 11-16: 예전엔 BASIC_ISO_DATE ("…+0900") 로 서비스의 같은 실수를 따라 해서 시험이 못 잡았음
    }

    @Test
    @SuppressWarnings("unchecked")
    void 시도17곳_지금날씨와_특보() {
        WeatherService s = new WeatherService("abc/def==", url -> url.contains("getUltraSrtNcst") ? NCST
            : url.contains("getVilageFcst") ? FCST.formatted(today()) : WARN);
        Map<String, Object> r = s.regions();
        List<Map<String, Object>> regions = (List<Map<String, Object>>) r.get("regions");
        assertEquals(17, regions.size());
        Map<String, Object> seoul = regions.get(0);
        assertEquals("seoul", seoul.get("id"));
        assertEquals(8, seoul.get("temp"));          // 실황 7.6 → 8
        assertEquals(-1, seoul.get("min"));
        assertEquals(12, seoul.get("max"));
        assertEquals("구름 많음", seoul.get("sky"));
        assertEquals(20, seoul.get("rain_prob"));
        assertEquals(55.0, seoul.get("humidity"));
        assertNull(seoul.get("warning"));
        assertEquals("영하 기온 · 서리·냉해 주의, 보온 대비", seoul.get("note"));
        Map<String, Object> gangwon = regions.stream().filter(x -> "gangwon".equals(x.get("id"))).findFirst().orElseThrow();
        assertEquals("강풍주의보 외 1건", gangwon.get("warning"));
        Map<String, Object> jeju = regions.stream().filter(x -> "jeju".equals(x.get("id"))).findFirst().orElseThrow();
        assertEquals("강풍주의보", jeju.get("warning"));
        assertTrue(((String) r.get("base_time")).endsWith(":00:00+09:00"));
    }

    @Test
    void 키가_없으면_503() {
        ResponseStatusException e = assertThrows(ResponseStatusException.class, () -> new WeatherService("", u -> "").regions());
        assertEquals(503, e.getStatusCode().value());
    }

    @Test
    void 키_오류는_502() {
        WeatherService s = new WeatherService("k", u -> "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE ERROR</errMsg></cmmMsgHeader></OpenAPI_ServiceResponse>");
        assertEquals(502, assertThrows(ResponseStatusException.class, s::regions).getStatusCode().value());
    }

    /** 11-16: 기상청에 보내는 날짜는 숫자 8자리만 (예전엔 "20261116+0900" 이 가서 모두 거절됨) */
    @Test
    void sends_plain_eight_digit_dates() {
        List<String> urls = new java.util.concurrent.CopyOnWriteArrayList<>();
        WeatherService s = new WeatherService("abc/def==", url -> {
            urls.add(url);
            return url.contains("getUltraSrtNcst") ? NCST : url.contains("getVilageFcst") ? FCST.formatted(today()) : WARN;
        });
        s.regions();
        List<String> dates = urls.stream().filter(u -> u.contains("base_date="))
            .map(u -> u.replaceAll(".*base_date=([^&]*).*", "$1")).toList();
        assertFalse(dates.isEmpty());
        dates.forEach(d -> assertTrue(d.matches("\\d{8}"), "base_date=" + d));
    }
}
