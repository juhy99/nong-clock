package com.farm.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 지금 날씨 (11-14) — docs/06_api_spec.md 2-7 GET /api/weather/regions.
 * 기상청 단기예보(초단기실황 + 단기예보) · 기상특보를 공공데이터포털(apis.data.go.kr)에서 시·도 17곳 대표 지점으로 받아 10분 캐시.
 * 변환 규칙은 화면 테스트 모드 코드(frontend/src/api/live/kmaWeather.js)를 그대로 옮김. 키: 환경 변수 DATA_GO_KR_KEY (Decoding 권장, Encoding 도 됨)
 * 지난 날씨(관측 기록·평년 대비)는 날씨 수집기가 만든 파일(/data/weather/...)을 화면이 따로 읽는다 — 이 API 는 "지금"만.
 */
@Service
public class WeatherService {
    private static final ZoneId KST = ZoneId.of("Asia/Seoul");
    private static final String BASE = "https://apis.data.go.kr/1360000";
    private static final Duration TTL = Duration.ofMinutes(10);
    /** 11-16: yyyyMMdd. 예전엔 BASIC_ISO_DATE 를 썼는데 ZonedDateTime 이면 "20261116+0900" 처럼 시간대가 붙어
     *  기상청이 APPLICATION_ERROR 로 거절 → 지금 날씨가 한 번도 안 나왔음 */
    static final DateTimeFormatter YMD = DateTimeFormatter.ofPattern("yyyyMMdd");

    /** 시·도 id (지도 데이터 id) → [이름, nx, ny] (시·도청 소재지 격자) */
    private static final Map<String, Object[]> REGIONS = new LinkedHashMap<>();
    static {
        Object[][] r = {
            {"seoul", "서울", 60, 127}, {"busan", "부산", 98, 76}, {"daegu", "대구", 89, 90}, {"incheon", "인천", 55, 124},
            {"gwangju", "광주", 58, 74}, {"daejeon", "대전", 67, 100}, {"ulsan", "울산", 102, 84}, {"sejong", "세종", 66, 103},
            {"gyeonggi", "경기", 60, 121}, {"gangwon", "강원", 73, 134}, {"north-chungcheong", "충북", 69, 106},
            {"south-chungcheong", "충남", 55, 106}, {"north-jeolla", "전북", 63, 89}, {"south-jeolla", "전남", 51, 67},
            {"north-gyeongsang", "경북", 91, 106}, {"south-gyeongsang", "경남", 90, 77}, {"jeju", "제주", 52, 38},
        };
        for (Object[] x : r) REGIONS.put((String) x[0], new Object[]{x[1], x[2], x[3]});
    }

    /** 특보 글에서 시·도를 찾을 이름 (괄호 안 세부 지역은 지우고 찾음: "경기도(광주…)" 가 광주광역시로 잡히지 않게) */
    private static final Map<String, List<String>> WARN_NAMES = Map.ofEntries(
        Map.entry("seoul", List.of("서울")), Map.entry("busan", List.of("부산")), Map.entry("daegu", List.of("대구")),
        Map.entry("incheon", List.of("인천")), Map.entry("gwangju", List.of("광주")), Map.entry("daejeon", List.of("대전")),
        Map.entry("ulsan", List.of("울산")), Map.entry("sejong", List.of("세종")), Map.entry("gyeonggi", List.of("경기")),
        Map.entry("gangwon", List.of("강원")), Map.entry("north-chungcheong", List.of("충청북도", "충북")),
        Map.entry("south-chungcheong", List.of("충청남도", "충남")), Map.entry("north-jeolla", List.of("전라북도", "전북")),
        Map.entry("south-jeolla", List.of("전라남도", "전남")), Map.entry("north-gyeongsang", List.of("경상북도", "경북")),
        Map.entry("south-gyeongsang", List.of("경상남도", "경남")), Map.entry("jeju", List.of("제주")));

    private static final Map<Integer, String[]> SKY = Map.of(1, new String[]{"☀️", "맑음"}, 3, new String[]{"⛅", "구름 많음"}, 4, new String[]{"☁️", "흐림"});
    private static final Map<Integer, String[]> PTY = Map.of(1, new String[]{"🌧️", "비"}, 2, new String[]{"🌨️", "비/눈"}, 3, new String[]{"❄️", "눈"},
        4, new String[]{"🌦️", "소나기"}, 5, new String[]{"🌧️", "빗방울"}, 6, new String[]{"🌨️", "빗방울눈날림"}, 7, new String[]{"❄️", "눈날림"});

    private final String key;
    // 11-16: HTTP/1.1 로 고정 — 공공데이터포털은 HTTP/2 협상이 들쭉날쭉해서 (curl 은 되는데 자바만 실패하는 경우 대비)
    private final HttpClient http = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(5)).build();
    /** 주소 → 응답 글 (시험에서 바꿔 끼움). 기본은 실제 호출 */
    private final java.util.function.Function<String, String> fetch;
    private final ObjectMapper json = new ObjectMapper();
    private final ExecutorService pool = Executors.newFixedThreadPool(4); // 공공데이터포털 초당 호출 제한 대비 4개씩

    private volatile Map<String, Object> cached;
    private volatile long cachedAt;

    @org.springframework.beans.factory.annotation.Autowired
    public WeatherService(@Value("${weather.data-go-kr-key:}") String key) {
        this(key, null);
    }

    WeatherService(String key, java.util.function.Function<String, String> fetch) {
        this.key = key == null ? "" : key.trim();
        this.fetch = fetch != null ? fetch : this::get;
    }

    private String get(String url) {
        try {
            return http.send(HttpRequest.newBuilder(URI.create(url)).timeout(Duration.ofSeconds(10)).GET().build(),
                HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8)).body();
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "기상청에 연결하지 못했어요: " + why(e));
        }
    }

    /** 오류 이유 (종류 + 문장). 키가 문장에 섞여 나오지 않게 가림 */
    private String why(Exception e) {
        String m = e.getClass().getSimpleName() + (e.getMessage() == null ? "" : " " + e.getMessage());
        if (!key.isEmpty()) m = m.replace(key, "***").replace(URLEncoder.encode(key, StandardCharsets.UTF_8), "***");
        return m.length() > 200 ? m.substring(0, 200) : m;
    }

    /** { base_time, regions: [{ id, name, temp, min, max, icon, sky, rain_prob, humidity, wind, soil_temp, warning, note }] } */
    public synchronized Map<String, Object> regions() {
        if (cached != null && System.currentTimeMillis() - cachedAt < TTL.toMillis()) return cached;
        if (key.isEmpty())
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "날씨 키가 없어요 (서버 .env 의 DATA_GO_KR_KEY)");
        ZonedDateTime now = ZonedDateTime.now(KST);
        // 초단기실황: 매시 정각 자료가 40분쯤 올라오므로 40분 전 기준 정각
        ZonedDateTime n = now.minusMinutes(40);
        String ncstDate = n.format(YMD), ncstTime = String.format("%02d00", n.getHour());
        // 오늘 최저·최고가 모두 든 단기예보: 오늘 02시 발표 (02:10 전이면 어제 23시 발표)
        String today = now.format(YMD);
        boolean after = now.getHour() > 2 || (now.getHour() == 2 && now.getMinute() >= 10);
        String fcstDate = after ? today : now.minusDays(1).format(YMD), fcstTime = after ? "0200" : "2300";
        String hourNow = String.format("%02d00", now.getHour());

        Map<String, String> warn = warnings();
        List<Future<Map<String, Object>>> jobs = new ArrayList<>();
        for (var e : REGIONS.entrySet())
            jobs.add(pool.submit(() -> region(e.getKey(), e.getValue(), ncstDate, ncstTime, fcstDate, fcstTime, today, hourNow)));
        List<Map<String, Object>> out = new ArrayList<>();
        try {
            for (var j : jobs) {
                Map<String, Object> r = j.get(30, TimeUnit.SECONDS);
                String w = warn.get((String) r.get("id"));
                r.put("warning", w);
                r.put("note", farmNote((Integer) r.get("min"), (Integer) r.get("max"), (Integer) r.get("rain_prob"), (Double) r.get("humidity"), w));
                out.add(r);
            }
        } catch (ExecutionException ex) {
            Throwable c = ex.getCause();
            if (c instanceof ResponseStatusException rse) throw rse;
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "기상청 날씨를 받지 못했어요: " + c.getMessage());
        } catch (InterruptedException | TimeoutException ex) {
            throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT, "기상청 응답이 늦어요. 잠시 뒤 다시 시도해 주세요.");
        }
        Map<String, Object> res = new LinkedHashMap<>();
        res.put("base_time", String.format("%s-%s-%sT%s:00:00+09:00", ncstDate.substring(0, 4), ncstDate.substring(4, 6), ncstDate.substring(6), ncstTime.substring(0, 2)));
        res.put("regions", out);
        cached = res;
        cachedAt = System.currentTimeMillis();
        return res;
    }

    private Map<String, Object> region(String id, Object[] info, String ncstDate, String ncstTime, String fcstDate, String fcstTime, String today, String hourNow) {
        int nx = (Integer) info[1], ny = (Integer) info[2];
        List<JsonNode> now = call("/VilageFcstInfoService_2.0/getUltraSrtNcst", Map.of("numOfRows", "20", "nx", "" + nx, "ny", "" + ny, "base_date", ncstDate, "base_time", ncstTime));
        List<JsonNode> rows = call("/VilageFcstInfoService_2.0/getVilageFcst", Map.of("numOfRows", "1000", "nx", "" + nx, "ny", "" + ny, "base_date", fcstDate, "base_time", fcstTime));
        // 관측 결측은 +900 이상·-900 이하로 온다
        Map<String, Double> obs = new HashMap<>();
        for (JsonNode r : now) {
            double v = r.path("obsrValue").asDouble(Double.NaN);
            obs.put(r.path("category").asText(), Math.abs(v) >= 900 ? Double.NaN : v);
        }
        List<JsonNode> td = rows.stream().filter(r -> today.equals(r.path("fcstDate").asText())).toList();
        String tmn = pick(td, "TMN"), tmx = pick(td, "TMX");
        List<Double> temps = td.stream().filter(r -> "TMP".equals(r.path("category").asText())).map(r -> r.path("fcstValue").asDouble()).toList();
        double ptyObs = obs.getOrDefault("PTY", Double.NaN);
        int ptyNow = !Double.isNaN(ptyObs) && ptyObs > 0 ? (int) ptyObs : toInt(at(td, "PTY", hourNow), 0);
        String[] icon = PTY.getOrDefault(ptyNow, SKY.getOrDefault(toInt(at(td, "SKY", hourNow), -1), new String[]{"🌤️", "-"}));
        double t1h = obs.getOrDefault("T1H", Double.NaN), reh = obs.getOrDefault("REH", Double.NaN), wsd = obs.getOrDefault("WSD", Double.NaN);
        String tmp = at(td, "TMP", hourNow), pop = at(td, "POP", hourNow);

        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", id);
        m.put("name", info[0]);
        m.put("temp", !Double.isNaN(t1h) ? (Integer) (int) Math.round(t1h) : tmp != null ? (Integer) (int) Math.round(Double.parseDouble(tmp)) : null);
        m.put("min", tmn != null ? (Integer) (int) Math.round(Double.parseDouble(tmn)) : temps.isEmpty() ? null : (Integer) (int) Math.round(Collections.min(temps)));
        m.put("max", tmx != null ? (Integer) (int) Math.round(Double.parseDouble(tmx)) : temps.isEmpty() ? null : (Integer) (int) Math.round(Collections.max(temps)));
        m.put("icon", icon[0]);
        m.put("sky", icon[1]);
        m.put("rain_prob", pop != null ? (Integer) toInt(pop, 0) : null);
        m.put("humidity", Double.isNaN(reh) ? null : (Double) reh);
        m.put("wind", Double.isNaN(wsd) ? null : (Double) wsd);
        m.put("soil_temp", null); // 단기예보에는 지온이 없음
        return m;
    }

    private static String pick(List<JsonNode> rows, String cat) {
        return rows.stream().filter(r -> cat.equals(r.path("category").asText())).map(r -> r.path("fcstValue").asText()).findFirst().orElse(null);
    }

    /** 지금 이후 가장 가까운 예보 시각 값 (없으면 그날 마지막 값) */
    private static String at(List<JsonNode> rows, String cat, String hourNow) {
        List<JsonNode> c = rows.stream().filter(r -> cat.equals(r.path("category").asText())).toList();
        return c.stream().filter(r -> r.path("fcstTime").asText().compareTo(hourNow) >= 0).map(r -> r.path("fcstValue").asText()).findFirst()
            .orElse(c.isEmpty() ? null : c.get(c.size() - 1).path("fcstValue").asText());
    }

    private static int toInt(String s, int d) {
        try {
            return s == null ? d : (int) Math.round(Double.parseDouble(s));
        } catch (NumberFormatException e) {
            return d;
        }
    }

    /** 농사 한 줄 조언 (화면 테스트 모드 farmNote 와 같은 규칙) */
    static String farmNote(Integer min, Integer max, Integer rainProb, Double humidity, String warning) {
        if (warning != null) return warning + " 발효 중 · 시설물·작물 피해 대비";
        if (min != null && min <= 0) return "영하 기온 · 서리·냉해 주의, 보온 대비";
        if (max != null && max >= 33) return "고온 · 차광·관수 필요";
        if (rainProb != null && rainProb >= 60) return "강수 예보 · 수확 일정 조정 권장";
        if (humidity != null && humidity < 35) return "건조한 날씨 · 노지 관수 필요";
        if (min != null && max != null && max - min >= 12) return "일교차 큼 · 엽채류 냉해 주의";
        return "작물 생육에 무난한 날씨";
    }

    /** 특보 발효현황 → { 지역 id: "강풍주의보" | "강풍주의보 외 1건" } (실패해도 날씨는 보여주도록 빈 값) */
    private Map<String, String> warnings() {
        try {
            StringBuilder text = new StringBuilder();
            for (JsonNode r : call("/WthrWrnInfoService/getPwnStatus", Map.of("numOfRows", "10"))) text.append(r.path("t6").asText("")).append('\n');
            Map<String, List<String>> out = new HashMap<>();
            Pattern p = Pattern.compile("^\\s*o\\s*([^:]+?)\\s*:\\s*(.+)$");
            for (String line : text.toString().split("\\r?\\n")) {
                Matcher m = p.matcher(line);
                if (!m.find()) continue;
                String name = m.group(1).replaceAll("\\s", "");
                String areas = m.group(2).replaceAll("\\([^)]*\\)", "");
                for (var e : WARN_NAMES.entrySet())
                    if (e.getValue().stream().anyMatch(areas::contains)) {
                        List<String> l = out.computeIfAbsent(e.getKey(), k -> new ArrayList<>());
                        if (!l.contains(name)) l.add(name);
                    }
            }
            Map<String, String> res = new HashMap<>();
            out.forEach((id, l) -> res.put(id, l.size() > 1 ? l.get(0) + " 외 " + (l.size() - 1) + "건" : l.get(0)));
            return res;
        } catch (RuntimeException e) {
            return Map.of();
        }
    }

    private List<JsonNode> call(String path, Map<String, String> params) {
        // Decoding 키는 인코딩해서, Encoding 키(%가 들어 있음)는 그대로
        String sk = key.contains("%") ? key : URLEncoder.encode(key, StandardCharsets.UTF_8);
        StringBuilder q = new StringBuilder("?serviceKey=").append(sk).append("&pageNo=1&dataType=JSON");
        params.forEach((k, v) -> q.append('&').append(k).append('=').append(URLEncoder.encode(v, StandardCharsets.UTF_8)));
        try {
            String body = fetch.apply(BASE + path + q);
            if (body.trim().startsWith("<"))  // 키 오류는 XML(OpenAPI_ServiceResponse)로 온다
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "공공데이터포털 키 오류 (DATA_GO_KR_KEY 확인)");
            JsonNode d = json.readTree(body);
            String code = d.path("response").path("header").path("resultCode").asText();
            if ("03".equals(code)) return List.of(); // NO_DATA
            if (!"00".equals(code))
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "기상청: " + d.path("response").path("header").path("resultMsg").asText("응답 형식이 다릅니다"));
            JsonNode item = d.path("response").path("body").path("items").path("item");
            List<JsonNode> list = new ArrayList<>();
            if (item.isArray()) item.forEach(list::add);
            else if (!item.isMissingNode()) list.add(item);
            return list;
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "기상청에 연결하지 못했어요: " + why(e));
        }
    }
}
