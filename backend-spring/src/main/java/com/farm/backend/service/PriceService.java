package com.farm.backend.service;

import com.farm.backend.repository.PriceSql;

import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 시세·수급 화면(/market)용 조회 — docs/06_api_spec.md 2-1 · 2-15 와 같은 모양으로 돌려준다 (2026-11-09).
 * 도매 시세는 국산만 (수입은 출하지역 표의 '수입' 줄). 읽는 표: price_daily · price_origin_daily · price_unit_daily · retail_price_daily · item · market · region · variety_unit (수집기 collector/daily 가 채움)
 * 계산 규칙은 ml-api/app/services/price_db.py 와 같다 (두 결과가 같은지 비교해 확인함).
 */
@Service
public class PriceService {
    public static final List<String> GRADES = List.of("SPECIAL", "HIGH", "MID", "LOW", "ALL");
    private static final String[] DEKAD = {"상순", "중순", "하순"};

    private final PriceSql db;

    public PriceService(PriceSql db) {
        this.db = db;
    }

    // ───────── 작은 도움 함수 ─────────
    static LocalDate date(Object v) {
        if (v == null) return null;
        if (v instanceof LocalDate d) return d;
        if (v instanceof java.sql.Date d) return d.toLocalDate();
        if (v instanceof java.util.Date d) return new java.sql.Date(d.getTime()).toLocalDate();
        return LocalDate.parse(v.toString().substring(0, 10));
    }

    static Double num(Object v) {
        if (v == null) return null;
        if (v instanceof Number n) return n.doubleValue();
        return new BigDecimal(v.toString()).doubleValue();
    }

    static Integer won(Object v) {
        Double d = num(v);
        return d == null ? null : (int) Math.round(d);
    }

    static Double pct(Integer now, Integer prev) {
        if (now == null || prev == null || prev == 0) return null;
        return round1((now - prev) * 100.0 / prev);
    }

    static Double pct(Long now, Long prev) {
        if (now == null || prev == null || prev == 0) return null;
        return round1((now - prev) * 100.0 / prev);
    }

    /** 파이썬 round(x, 1) 과 같은 반올림 (짝수 쪽 맞춤은 무시해도 0.1 단위라 화면에는 차이 없음) */
    static Double round1(double x) {
        return Math.round(x * 10) / 10.0;
    }

    static Double ton(Object kg) {
        Double d = num(kg);
        return d == null ? null : round1(d / 1000);
    }

    static Integer chg(Integer now, Integer prev) {
        return now == null || prev == null ? null : now - prev;
    }

    static boolean isTrue(Object v) {
        return v instanceof Boolean b ? b : v != null && Set.of("t", "true", "True").contains(v.toString());
    }

    private static String iso(LocalDate d) {
        return d == null ? null : d.toString();
    }

    private static Map<String, Object> obj(Object... kv) {
        Map<String, Object> m = new LinkedHashMap<>();
        for (int i = 0; i < kv.length; i += 2) m.put((String) kv[i], kv[i + 1]);
        return m;
    }

    private static Map<String, Object> p(Object... kv) {
        return obj(kv);
    }

    // ───────── 날짜 ─────────
    /** upto(없으면 최근) 이전의 거래일 n개, 오래된 → 최근. 그 품목·시장(또는 품종의 예측 단위 중 하나)에 거래가 있던 날만 */
    List<LocalDate> tradeDates(String item, String market, LocalDate upto, int n, List<Integer> unitIds) {
        String cond = upto == null ? "" : " AND date <= :d";
        List<Map<String, Object>> rows = unitIds != null
                ? db.rows("SELECT DISTINCT date FROM price_unit_daily WHERE unit_id IN (:u)" + cond + " ORDER BY date DESC LIMIT :n",
                        p("u", unitIds, "d", upto, "n", n))
                : db.rows("SELECT DISTINCT date FROM price_daily WHERE item_code = :i AND market_code = :m" + cond + " ORDER BY date DESC LIMIT :n",
                        p("i", item, "m", market, "d", upto, "n", n));
        return rows.stream().map(r -> date(r.get("date"))).sorted().collect(Collectors.toList());
    }

    /** 예측 단위 이름들 → DB 의 unit_id 들 (DB 에 없는 이름은 뺌, 하나도 없으면 빈 목록) */
    public List<Integer> unitIdsOf(List<String> unitNames) {
        if (unitNames == null || unitNames.isEmpty()) return List.of();
        return db.rows("SELECT unit_id FROM variety_unit WHERE unit_name IN (:n) ORDER BY unit_id", p("n", unitNames)).stream()
                .map(r -> num(r.get("unit_id")).intValue()).collect(Collectors.toList());
    }

    /** 품종 시세 한 날 값: 들어가는 예측 단위들의 금액 합 ÷ 물량 합 (단위 하나면 그 단위 값과 같음). 금액이 없으면 단순 평균 */
    private static final String UNIT_PRICE = "COALESCE(ROUND(SUM(amount_won) / NULLIF(SUM(CASE WHEN amount_won IS NOT NULL THEN volume_kg END), 0)), ROUND(AVG(price)))";

    // ───────── 소매가 (KAMIS, retail_price_daily) ─────────
    /** 품목의 소매가 기록 (날짜 → 원/kg). KAMIS 는 조사일이 도매 거래일과 달라서, 그날 또는 3일 안 앞선 조사일 값을 쓴다 */
    private TreeMap<LocalDate, Integer> retail(String item, LocalDate from, LocalDate to) {
        TreeMap<LocalDate, Integer> m = new TreeMap<>();
        for (Map<String, Object> r : db.rows("SELECT date, price FROM retail_price_daily WHERE item_code = :i AND date BETWEEN :a AND :b",
                p("i", item, "a", from.minusDays(3), "b", to)))
            m.put(date(r.get("date")), won(r.get("price")));
        return m;
    }

    static Integer at(TreeMap<LocalDate, Integer> m, LocalDate d) {
        if (d == null) return null;
        Map.Entry<LocalDate, Integer> e = m.floorEntry(d);
        return e == null || e.getKey().isBefore(d.minusDays(3)) ? null : e.getValue();
    }

    /** 1년 전 무렵(364~394일 전) 가장 가까운 소매가 */
    static Integer yearAgo(TreeMap<LocalDate, Integer> m, LocalDate base) {
        Map.Entry<LocalDate, Integer> e = m.floorEntry(base.minusDays(364));
        return e == null || e.getKey().isBefore(base.minusDays(394)) ? null : e.getValue();
    }

    // ───────── 2-1 오늘 시세 ─────────
    public Map<String, Object> today() {
        List<Map<String, Object>> ds = db.rows("SELECT date FROM (SELECT DISTINCT date FROM price_daily WHERE market_code = 'national' AND grade = 'HIGH' "
                + "ORDER BY date DESC LIMIT 2) x ORDER BY date", Map.of());
        if (ds.isEmpty())
            return obj("base_date", null, "compared_date", null, "market", "national", "grade", "HIGH", "unit", "kg", "items", List.of());
        List<LocalDate> days = ds.stream().map(r -> date(r.get("date"))).toList();
        LocalDate base = days.get(days.size() - 1), prev = days.size() > 1 ? days.get(0) : null;
        List<Map<String, Object>> rows = db.rows("SELECT i.item_code, i.name, i.emoji, i.category, i.sort_order, p.date, p.price FROM item i "
                + "LEFT JOIN price_daily p ON p.item_code = i.item_code AND p.market_code = 'national' AND p.grade = 'HIGH' "
                + "AND p.date IN (:b, :p) ORDER BY i.sort_order", p("b", base, "p", prev != null ? prev : base));
        Map<String, Map<String, Object>> items = new LinkedHashMap<>();
        for (Map<String, Object> r : rows) {
            Map<String, Object> x = items.computeIfAbsent((String) r.get("item_code"), k -> obj("item", k, "name", r.get("name"),
                    "emoji", r.get("emoji"), "category", r.get("category"), "price", null, "prev_price", null));
            LocalDate d = date(r.get("date"));
            if (d == null) continue;
            if (d.equals(base)) x.put("price", won(r.get("price")));
            else if (d.equals(prev)) x.put("prev_price", won(r.get("price")));
        }
        Map<String, Integer> rmap = new HashMap<>();   // 기준일 또는 3일 안 앞선 조사일의 전국 소매가
        for (Map<String, Object> r : db.rows("SELECT DISTINCT ON (item_code) item_code, price FROM retail_price_daily WHERE date BETWEEN :a AND :b "
                + "ORDER BY item_code, date DESC", p("a", base.minusDays(3), "b", base)))
            rmap.put((String) r.get("item_code"), won(r.get("price")));
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> x : items.values()) {
            Integer price = (Integer) x.get("price"), before = (Integer) x.get("prev_price");
            x.put("change", chg(price, before));
            x.put("change_pct", pct(price, before));
            Integer rp = rmap.get((String) x.get("item"));
            x.put("retail_price", rp);
            x.put("margin_pct", rp == null || price == null || price == 0 ? null : Math.round((rp - price) * 100.0 / price));
            out.add(x);
        }
        return obj("base_date", iso(base), "compared_date", iso(prev), "market", "national", "grade", "HIGH", "unit", "kg", "items", out);
    }

    // ───────── 2-15 도매시장 목록 ─────────
    public List<Map<String, Object>> markets() {
        List<Map<String, Object>> ms = db.rows("SELECT m.market_code, m.name, r.name AS sido, m.sigungu, m.lat, m.lon FROM market m "
                + "LEFT JOIN region r ON r.region_id = m.region_id WHERE m.is_active AND m.market_code <> 'national' ORDER BY m.market_code", Map.of());
        List<Map<String, Object>> last = db.rows("SELECT max(date) AS d FROM price_daily WHERE market_code = 'national'", Map.of());
        LocalDate lastD = last.isEmpty() || last.get(0).get("d") == null ? LocalDate.now() : date(last.get(0).get("d"));
        String q = "SELECT market_code, item_code, sum(volume_kg) AS v FROM price_daily WHERE grade = 'ALL' AND market_code <> 'national' "
                + "AND date > :d GROUP BY market_code, item_code";
        Map<String, List<String>> items = new HashMap<>();
        for (Map<String, Object> r : db.rows(q, p("d", lastD.minusDays(365))))
            items.computeIfAbsent((String) r.get("market_code"), k -> new ArrayList<>()).add((String) r.get("item_code"));
        Map<String, Object[]> top = new HashMap<>();
        for (Map<String, Object> r : db.rows(q, p("d", lastD.minusDays(30)))) {
            String c = (String) r.get("market_code");
            double v = num(r.get("v"));
            if (!top.containsKey(c) || v > (double) top.get(c)[1]) top.put(c, new Object[]{r.get("item_code"), v});
        }
        List<Map<String, Object>> out = new ArrayList<>();
        out.add(obj("code", "national", "name", "전국 도매시장 평균"));
        for (Map<String, Object> m : ms) {
            String c = (String) m.get("market_code");
            List<String> it = new ArrayList<>(items.getOrDefault(c, List.of()));
            Collections.sort(it);
            out.add(obj("code", c, "name", m.get("name"), "sido", m.get("sido"), "sigungu", m.get("sigungu"),
                    "lat", num(m.get("lat")), "lon", num(m.get("lon")), "top_item", top.containsKey(c) ? top.get(c)[0] : null, "items", it));
        }
        return out;
    }

    // ───────── 2-15 등급별 가격 ─────────
    private static Map<String, Object> card(Map<LocalDate, Integer> s, List<LocalDate> days, LocalDate base, LocalDate prev, Integer yearAgo) {
        Integer price = s.get(base), before = prev == null ? null : s.get(prev);
        List<Map<String, Object>> pts = new ArrayList<>();
        for (LocalDate d : days) pts.add(obj("date", iso(d), "price", s.get(d)));
        return obj("price", price, "prev_price", before, "change", chg(price, before), "change_pct", pct(price, before),
                "year_ago_pct", pct(price, yearAgo), "points", pts);
    }

    private static Map<String, Object> emptyRetail(List<LocalDate> days) {
        List<Map<String, Object>> pts = new ArrayList<>();
        for (LocalDate d : days) pts.add(obj("date", iso(d), "price", null));
        return obj("price", null, "prev_price", null, "change", null, "change_pct", null, "year_ago_pct", null, "points", pts);
    }

    public Map<String, Object> grades(String item, String market, LocalDate date, List<Integer> unitIds) {
        List<LocalDate> days = tradeDates(item, market, date, 5, unitIds);
        if (days.isEmpty())
            return obj("item", item, "market", market, "base_date", null, "compared_date", null, "unit", "kg", "grades", List.of(), "retail", emptyRetail(days));
        LocalDate base = days.get(days.size() - 1), prev = days.size() > 1 ? days.get(days.size() - 2) : null;
        LocalDate yaLo = base.minusDays(394), yaHi = base.minusDays(364);
        List<Map<String, Object>> grades = new ArrayList<>();
        if (unitIds != null) {   // 품종: 등급 구분이 없는 표 → 평균(ALL) 카드 하나
            Map<LocalDate, Integer> s = new HashMap<>();
            for (Map<String, Object> r : db.rows("SELECT date, " + UNIT_PRICE + " AS price FROM price_unit_daily WHERE unit_id IN (:u) AND date IN (:ds) GROUP BY date",
                    p("u", unitIds, "ds", days)))
                s.put(date(r.get("date")), won(r.get("price")));
            List<Map<String, Object>> ya = db.rows("SELECT date, " + UNIT_PRICE + " AS price FROM price_unit_daily WHERE unit_id IN (:u) AND date BETWEEN :a AND :b "
                    + "GROUP BY date ORDER BY date DESC LIMIT 1", p("u", unitIds, "a", yaLo, "b", yaHi));
            Map<String, Object> g = obj("grade", "ALL");
            g.putAll(card(s, days, base, prev, ya.isEmpty() ? null : won(ya.get(0).get("price"))));
            grades.add(g);
        } else {
            Map<String, Map<LocalDate, Integer>> by = new LinkedHashMap<>();
            for (String g : GRADES) by.put(g, new HashMap<>());
            for (Map<String, Object> r : db.rows("SELECT date, grade, price FROM price_daily WHERE item_code = :i AND market_code = :m AND date IN (:ds)",
                    p("i", item, "m", market, "ds", days))) {
                Map<LocalDate, Integer> s = by.get((String) r.get("grade"));
                if (s != null) s.put(date(r.get("date")), won(r.get("price")));
            }
            Map<String, Integer> yad = new HashMap<>();
            for (Map<String, Object> r : db.rows("SELECT DISTINCT ON (grade) grade, price FROM price_daily WHERE item_code = :i AND market_code = :m "
                    + "AND date BETWEEN :a AND :b ORDER BY grade, date DESC", p("i", item, "m", market, "a", yaLo, "b", yaHi)))
                yad.put((String) r.get("grade"), won(r.get("price")));
            for (String g : GRADES) {
                Map<String, Object> x = obj("grade", g);
                x.putAll(card(by.get(g), days, base, prev, yad.get(g)));
                grades.add(x);
            }
        }
        // 최근 30일 그 시장에서 등급마다 거래된 날 수 (11-09): 시장마다 등급을 붙이는 방식이 달라(예: 특·보통만) 화면이 거의 빈 등급을 숨김
        Map<String, Long> d30 = new HashMap<>();
        if (unitIds == null)
            for (Map<String, Object> r : db.rows("SELECT grade, count(*) AS n FROM price_daily WHERE item_code = :i AND market_code = :m "
                    + "AND date BETWEEN :a AND :b GROUP BY grade", p("i", item, "m", market, "a", base.minusDays(29), "b", base)))
                d30.put((String) r.get("grade"), num(r.get("n")).longValue());
        else
            d30.put("ALL", (long) days.size());
        for (Map<String, Object> g : grades) g.put("days_30", d30.getOrDefault((String) g.get("grade"), 0L));
        TreeMap<LocalDate, Integer> rt = retail(item, base.minusDays(400), base);
        Map<LocalDate, Integer> rs = new HashMap<>();
        for (LocalDate d : days) rs.put(d, at(rt, d));
        return obj("item", item, "market", market, "base_date", iso(base), "compared_date", iso(prev), "unit", "kg", "grades", grades,
                "days_30", d30.getOrDefault("ALL", 0L), "retail", card(rs, days, base, prev, yearAgo(rt, base)));
    }

    // ───────── 2-15 가격 추이 ─────────
    public Map<String, Object> history(String item, String market, String grade, LocalDate date, int days, List<Integer> unitIds) {
        List<LocalDate> ds = tradeDates(item, market, date, days + 1, unitIds);
        Map<LocalDate, Integer[]> pr = new HashMap<>();   // [가격, 최고, 최저]
        Map<LocalDate, Object> vol = new HashMap<>();
        if (!ds.isEmpty()) {
            if (unitIds != null) {
                for (Map<String, Object> r : db.rows("SELECT date, " + UNIT_PRICE + " AS price, SUM(volume_kg) AS volume_kg FROM price_unit_daily "
                        + "WHERE unit_id IN (:u) AND date IN (:ds) GROUP BY date", p("u", unitIds, "ds", ds))) {
                    LocalDate d = date(r.get("date"));
                    pr.put(d, new Integer[]{won(r.get("price")), null, null});
                    vol.put(d, r.get("volume_kg"));
                }
            } else {
                for (Map<String, Object> r : db.rows("SELECT date, grade, price, price_high, price_low, volume_kg FROM price_daily WHERE item_code = :i "
                        + "AND market_code = :m AND grade IN (:g, 'ALL') AND date IN (:ds)", p("i", item, "m", market, "g", grade, "ds", ds))) {
                    LocalDate d = date(r.get("date"));
                    if (grade.equals(r.get("grade"))) pr.put(d, new Integer[]{won(r.get("price")), won(r.get("price_high")), won(r.get("price_low"))});
                    if ("ALL".equals(r.get("grade"))) vol.put(d, r.get("volume_kg"));
                }
            }
        }
        Integer[] none = {null, null, null};
        TreeMap<LocalDate, Integer> rt = ds.isEmpty() ? new TreeMap<>() : retail(item, ds.get(0), ds.get(ds.size() - 1));
        List<Map<String, Object>> pts = new ArrayList<>();
        for (int k = 1; k < ds.size(); k++) {
            LocalDate d = ds.get(k), b = ds.get(k - 1);
            Integer[] x = pr.getOrDefault(d, none);
            Integer before = pr.getOrDefault(b, none)[0];
            pts.add(obj("date", iso(d), "price", x[0], "change", chg(x[0], before), "change_pct", pct(x[0], before),
                    "high", x[1], "low", x[2], "volume_t", ton(vol.get(d)), "retail", at(rt, d)));
        }
        if (ds.size() == 1) {   // 거래일이 하루뿐
            Integer[] x = pr.getOrDefault(ds.get(0), none);
            pts.add(obj("date", iso(ds.get(0)), "price", x[0], "change", null, "change_pct", null, "high", x[1], "low", x[2],
                    "volume_t", ton(vol.get(ds.get(0))), "retail", at(rt, ds.get(0))));
        }
        return obj("item", item, "market", market, "grade", unitIds != null ? "ALL" : grade, "unit", "kg", "points", pts);
    }

    // ───────── 2-15 출하지역별 가격 ─────────
    private List<LocalDate> originDates(String item, String market, LocalDate upto, int n) {
        String cond = upto == null ? "" : " AND date <= :d";
        return db.rows("SELECT DISTINCT date FROM price_origin_daily WHERE item_code = :i AND market_code = :m" + cond + " ORDER BY date DESC LIMIT :n",
                        p("i", item, "m", market, "d", upto, "n", n))
                .stream().map(r -> date(r.get("date"))).sorted().collect(Collectors.toList());
    }

    private static String regionName(Map<String, Object> r) {
        if (isTrue(r.get("is_import"))) return "수입";
        Object n = r.get("region");
        return n == null ? "기타" : n.toString();
    }

    public Map<String, Object> origins(String item, String market, LocalDate date) {
        List<LocalDate> ds = originDates(item, market, date, 2);
        if (ds.isEmpty())
            return obj("item", item, "market", market, "base_date", null, "compared_date", null, "unit", "kg", "regions", List.of());
        LocalDate base = ds.get(ds.size() - 1), prev = ds.size() > 1 ? ds.get(0) : null;
        Map<String, Object[]> now = new HashMap<>(), before = new HashMap<>();   // 지역 → [가격, 물량kg]
        for (Map<String, Object> r : db.rows("SELECT o.date, o.is_import, r.name AS region, o.price, o.volume_kg FROM price_origin_daily o "
                + "LEFT JOIN region r ON r.region_id = o.origin_region_id WHERE o.item_code = :i AND o.market_code = :m AND o.date IN (:ds)",
                p("i", item, "m", market, "ds", ds))) {
            Double v = num(r.get("volume_kg"));
            (date(r.get("date")).equals(base) ? now : before).put(regionName(r), new Object[]{won(r.get("price")), v == null ? 0.0 : v});
        }
        List<Map<String, Object>> regions = new ArrayList<>();
        now.entrySet().stream().sorted((a, b) -> Double.compare((double) b.getValue()[1], (double) a.getValue()[1])).forEach(e -> {
            Integer price = (Integer) e.getValue()[0];
            Integer b = before.containsKey(e.getKey()) ? (Integer) before.get(e.getKey())[0] : null;
            regions.add(obj("region", e.getKey(), "price", price, "change", chg(price, b), "change_pct", pct(price, b),
                    "high", null, "low", null, "volume_t", ton(e.getValue()[1])));   // 출하지역 표에는 최고·최저가 없음
        });
        return obj("item", item, "market", market, "base_date", iso(base), "compared_date", iso(prev), "unit", "kg", "regions", regions);
    }

    // ───────── 2-15 반입 동향 (순 = 10일) ─────────
    static LocalDate dekadStart(LocalDate d) {
        return d.withDayOfMonth(d.getDayOfMonth() <= 10 ? 1 : d.getDayOfMonth() <= 20 ? 11 : 21);
    }

    static String dekadLabel(LocalDate s) {
        return s.getMonthValue() + "월 " + DEKAD[s.getDayOfMonth() == 1 ? 0 : s.getDayOfMonth() == 11 ? 1 : 2];
    }

    private record Vol(LocalDate date, String region, double t) {}

    private List<Vol> originVolumes(String item, String market, LocalDate a, LocalDate b) {
        List<Vol> out = new ArrayList<>();
        for (Map<String, Object> r : db.rows("SELECT o.date, o.is_import, r.name AS region, o.volume_kg FROM price_origin_daily o "
                + "LEFT JOIN region r ON r.region_id = o.origin_region_id WHERE o.item_code = :i AND o.market_code = :m AND o.date BETWEEN :a AND :b",
                p("i", item, "m", market, "a", a, "b", b))) {
            Double v = num(r.get("volume_kg"));
            out.add(new Vol(date(r.get("date")), regionName(r), (v == null ? 0 : v) / 1000));
        }
        return out;
    }

    private static Map<String, Double> sumByRegion(List<Vol> rows) {
        Map<String, Double> s = new LinkedHashMap<>();
        for (Vol r : rows) s.merge(r.region(), r.t(), Double::sum);
        return s;
    }

    /** 파이썬 round() 처럼 반올림 (.5 는 짝수 쪽) — 두 API 숫자를 똑같이 맞추려고 */
    static long roundHalfEven(double x) {
        return Math.round(Math.rint(x));
    }

    public Map<String, Object> volumes(String item, String market, LocalDate date, int periods) {
        List<LocalDate> ds = originDates(item, market, date, 1);
        if (ds.isEmpty()) {
            Map<String, Object> blankTop = obj("region", "-", "volume_t", 0L, "share_pct", 0L, "year_ago_pct", null);
            return obj("item", item, "market", market, "unit", "톤", "periods", List.of(),
                    "summary", obj("period", "", "top", List.of(blankTop, blankTop), "others_t", 0L, "total_t", 0L, "change_t", 0L, "change_pct", null));
        }
        LocalDate end = ds.get(ds.size() - 1);
        LinkedList<LocalDate> starts = new LinkedList<>(List.of(dekadStart(end)));
        while (starts.size() < periods) starts.addFirst(dekadStart(starts.getFirst().minusDays(1)));
        List<Vol> rows = originVolumes(item, market, starts.getFirst(), end);
        List<Map<String, Object>> out = new ArrayList<>();
        List<Set<LocalDate>> dayset = new ArrayList<>();
        for (int i = 0; i < starts.size(); i++) {
            LocalDate s = starts.get(i), stop = i == starts.size() - 1 ? end : starts.get(i + 1).minusDays(1);
            List<Vol> part = rows.stream().filter(r -> !r.date().isBefore(s) && !r.date().isAfter(stop)).toList();
            List<Map.Entry<String, Double>> reg = sumByRegion(part).entrySet().stream()
                    .sorted((a, b) -> Double.compare(b.getValue(), a.getValue())).toList();
            double total = reg.stream().mapToDouble(Map.Entry::getValue).sum();
            List<Map<String, Object>> top = new ArrayList<>();
            for (int k = 0; k < 2; k++)
                top.add(k < reg.size() ? obj("region", reg.get(k).getKey(), "volume_t", roundHalfEven(reg.get(k).getValue())) : obj("region", "-", "volume_t", 0L));
            long tot = roundHalfEven(total);
            out.add(obj("period", dekadLabel(s), "start", iso(s), "end", iso(stop), "top1", top.get(0), "top2", top.get(1),
                    "others_t", tot - (long) top.get(0).get("volume_t") - (long) top.get(1).get("volume_t"), "total_t", tot));
            dayset.add(part.stream().map(Vol::date).collect(Collectors.toCollection(TreeSet::new)));
        }
        Map<String, Object> now = out.get(out.size() - 1);
        // 지난 순은 이번 순과 같은 거래일 수까지만 더해 비교
        long prevSame = 0;
        if (out.size() > 1) {
            LocalDate ps = LocalDate.parse((String) out.get(out.size() - 2).get("start")), pe = LocalDate.parse((String) out.get(out.size() - 2).get("end"));
            List<Vol> prevRows = rows.stream().filter(r -> !r.date().isBefore(ps) && !r.date().isAfter(pe)).toList();
            Set<LocalDate> keep = prevRows.stream().map(Vol::date).collect(Collectors.toCollection(TreeSet::new))
                    .stream().limit(dayset.get(dayset.size() - 1).size()).collect(Collectors.toSet());
            prevSame = roundHalfEven(prevRows.stream().filter(r -> keep.contains(r.date())).mapToDouble(Vol::t).sum());
        }
        // 전년 같은 순 (지역별)
        LocalDate s0 = LocalDate.parse((String) now.get("start")), e0 = LocalDate.parse((String) now.get("end"));
        Map<String, Double> ly = sumByRegion(originVolumes(item, market, s0.minusYears(1), e0.minusYears(1)));
        long tot = (long) now.get("total_t");
        List<Map<String, Object>> top = new ArrayList<>();
        for (String k : List.of("top1", "top2")) {
            @SuppressWarnings("unchecked") Map<String, Object> t = new LinkedHashMap<>((Map<String, Object>) now.get(k));
            long v = (long) t.get("volume_t");
            t.put("share_pct", roundHalfEven(v * 100.0 / (tot == 0 ? 1 : tot)));
            t.put("year_ago_pct", pct(v, roundHalfEven(ly.getOrDefault((String) t.get("region"), 0.0))));
            top.add(t);
        }
        return obj("item", item, "market", market, "unit", "톤", "periods", out,
                "summary", obj("period", now.get("period"), "top", top, "others_t", now.get("others_t"), "total_t", tot,
                        "change_t", tot - prevSame, "change_pct", pct(tot, prevSame)));
    }

    // ───────── 2-15 시장별 오늘 가격 (통합 검색) ─────────
    public Map<String, Object> compare(String item) {
        List<Map<String, Object>> rows = db.rows("SELECT DISTINCT ON (p.market_code) p.market_code, m.name, p.date, p.price, p.grade FROM price_daily p "
                + "JOIN market m ON m.market_code = p.market_code WHERE p.item_code = :i AND p.market_code <> 'national' "
                + "AND p.grade IN ('HIGH', 'ALL') AND p.date > (SELECT max(date) - 14 FROM price_daily WHERE market_code = 'national') "
                + "ORDER BY p.market_code, p.date DESC, (p.grade = 'HIGH') DESC", p("i", item));
        Map<String, Double> vol = new HashMap<>();
        for (Map<String, Object> r : db.rows("SELECT market_code, sum(volume_kg) AS v FROM price_daily WHERE item_code = :i AND grade = 'ALL' "
                + "AND market_code <> 'national' AND date > (SELECT max(date) - 30 FROM price_daily WHERE market_code = 'national') GROUP BY market_code", p("i", item)))
            vol.put((String) r.get("market_code"), num(r.get("v")));
        List<Map<String, Object>> ms = rows.stream()
                .sorted((a, b) -> Double.compare(vol.getOrDefault((String) b.get("market_code"), 0.0), vol.getOrDefault((String) a.get("market_code"), 0.0)))
                .limit(5).map(r -> obj("market", r.get("name"), "price", won(r.get("price")))).toList();
        return obj("item", item, "unit", "kg", "markets", ms);
    }

    // ───────── 시세 화면 맨 아래 "도매시장 · 산지" 두 카드 (11-12, 화면 PR #40) ─────────
    // 위에서 고른 시장과 상관없이 품목(또는 품종)만 · 최근 12달. 응답 모양은 frontend/src/mocks/market.js 의 mockMarketShare · mockAuctionHouses 와 같다
    private static final int TOP = 8;

    /**
     * 도매시장별 최근 12달 평균 경락가 · 물량 몫 (물량 많은 시장 8곳) + 물량 가중 평균(전체 시장).
     * 품목: price_daily(시장 × 품목, grade='ALL', 국산) — 그 품목 전국 마지막 거래일부터 365일.
     * 품종: price_unit_market_monthly(시장 × 예측 단위 × 달) — 마지막 달 포함 12달. 평균 경락가 = 금액 합 ÷ 물량 합
     */
    public Map<String, Object> marketShare(String item, List<Integer> unitIds) {
        List<Map<String, Object>> rows;
        Object from, to;
        if (unitIds != null) {
            Map<String, Object> span = db.rows("SELECT max(month) AS b FROM price_unit_market_monthly WHERE unit_id IN (:u)", p("u", unitIds)).get(0);
            LocalDate last = date(span.get("b"));
            if (last == null) return obj("item", item, "period", "최근 12달", "markets", List.of(), "market_count", 0, "weighted_avg", null, "sample", false);
            LocalDate first = last.minusMonths(11);
            rows = db.rows("SELECT u.market_code AS code, m.name AS market, sum(u.amount_won) AS a, sum(u.volume_kg) AS v FROM price_unit_market_monthly u "
                    + "JOIN market m ON m.market_code = u.market_code WHERE u.unit_id IN (:u) AND u.month BETWEEN :a AND :b GROUP BY u.market_code, m.name",
                    p("u", unitIds, "a", first, "b", last));
            from = iso(first); to = iso(last.plusMonths(1).minusDays(1));
        } else {
            Map<String, Object> span = db.rows("SELECT max(date) AS b FROM price_daily WHERE item_code = :i AND market_code = 'national' AND grade = 'ALL'", p("i", item)).get(0);
            LocalDate last = date(span.get("b"));
            if (last == null) return obj("item", item, "period", "최근 12달", "markets", List.of(), "market_count", 0, "weighted_avg", null, "sample", false);
            rows = db.rows("SELECT p.market_code AS code, m.name AS market, sum(p.amount_won) AS a, sum(p.volume_kg) AS v FROM price_daily p "
                    + "JOIN market m ON m.market_code = p.market_code WHERE p.item_code = :i AND p.grade = 'ALL' AND p.market_code <> 'national' "
                    + "AND p.date > :a AND p.date <= :b GROUP BY p.market_code, m.name", p("i", item, "a", last.minusDays(365), "b", last));
            from = iso(last.minusDays(364)); to = iso(last);
        }
        double va = 0, vv = 0;
        List<Map<String, Object>> ms = new ArrayList<>();
        for (Map<String, Object> r : rows) {
            Double a = num(r.get("a")), v = num(r.get("v"));
            if (a == null || v == null || v <= 0) continue;
            va += a; vv += v;
            ms.add(obj("market", r.get("market"), "code", r.get("code"), "price", (int) Math.round(a / v), "_v", v));
        }
        final double tot = vv;
        ms.sort((x, y) -> Double.compare((double) y.get("_v"), (double) x.get("_v")));
        ms.forEach(m -> m.put("share_pct", round1((double) m.remove("_v") * 100 / tot)));
        return obj("item", item, "period", "최근 12달", "from", from, "to", to, "markets", ms.subList(0, Math.min(TOP, ms.size())),
                "market_count", ms.size(), "weighted_avg", vv > 0 ? (int) Math.round(va / vv) : null, "variety_applied", unitIds != null, "sample", false);
    }

    /** 공판장 이름 → 그래프용 짧은 이름 (예: 군산원예농업협동조합 → 군산원예, 제주시농협농산물공판장 → 제주시) */
    static String shortName(String name) {
        if (name == null) return "";
        String s = name.replaceAll("(농업협동조합|원협|농협|축협|조합|공판장|\\().*$", "").trim();
        return s.isEmpty() ? name : s;
    }

    /**
     * 산지공판장 최근 12달 평균 경락가 · 23~25년 평균 · 물량 몫 (물량 많은 공판장 8곳). 표: producer_price_daily + producer(시·도).
     * 최근 12달 = 그 품목 산지 자료 마지막 날부터 365일. 품종별 산지 가격은 원자료에 없어서 품목 값 (variety_applied = false)
     */
    public Map<String, Object> auctionHouses(String item) {
        LocalDate last = date(db.rows("SELECT max(date) AS b FROM producer_price_daily WHERE item_code = :i AND producer_code <> 'national'", p("i", item)).get(0).get("b"));
        if (last == null) return obj("item", item, "period", "최근 12달", "past", "23~25년", "houses", List.of(), "sample", false);
        String q = "SELECT d.producer_code AS code, max(d.producer_name) AS name, max(r.sido) AS sido, sum(d.amount_won) AS a, sum(d.volume_kg) AS v "
                + "FROM producer_price_daily d LEFT JOIN producer r ON r.producer_code = d.producer_code "
                + "WHERE d.item_code = :i AND d.producer_code <> 'national' AND d.date BETWEEN :a AND :b GROUP BY d.producer_code";
        List<Map<String, Object>> now = db.rows(q, p("i", item, "a", last.minusDays(364), "b", last));
        Map<String, Integer> past = new HashMap<>();
        for (Map<String, Object> r : db.rows(q, p("i", item, "a", LocalDate.of(2023, 1, 1), "b", LocalDate.of(2025, 12, 31)))) {
            Double a = num(r.get("a")), v = num(r.get("v"));
            if (a != null && v != null && v > 0) past.put((String) r.get("code"), (int) Math.round(a / v));
        }
        double tot = now.stream().mapToDouble(r -> Optional.ofNullable(num(r.get("v"))).orElse(0.0)).sum();
        List<Map<String, Object>> hs = now.stream().filter(r -> num(r.get("v")) != null && num(r.get("v")) > 0 && num(r.get("a")) != null)
                .sorted((x, y) -> Double.compare(num(y.get("v")), num(x.get("v")))).limit(TOP)
                .map(r -> obj("name", r.get("name"), "short", shortName((String) r.get("name")), "sido", r.get("sido"),
                        "price", (int) Math.round(num(r.get("a")) / num(r.get("v"))), "past_price", past.get((String) r.get("code")),
                        "share_pct", round1(num(r.get("v")) * 100 / tot)))
                .collect(Collectors.toList());
        return obj("item", item, "period", "최근 12달", "past", "23~25년", "from", iso(last.minusDays(364)), "to", iso(last),
                "houses", hs, "variety_applied", false, "sample", false);
    }

    // ───────── 가격 예측 화면 "계절 패턴 · 월별 반입량" (11-13) ─────────
    /**
     * 월별 평균 경락가·반입량: 평년(올해 빼고 최근 5년, 해마다 그 달 값의 평균) · 올해 실제(마지막 거래 달까지) · 남은 달 예측(price_forecast_daily 의 그 달 하루 값 평균).
     * 품목: price_daily(전국, grade='ALL') — /ai 의 기준가와 같은 표. 품종: price_unit_daily 의 예측 단위들 금액 합 ÷ 물량 합.
     * 응답 모양은 frontend/src/mocks/seasonal.js 와 같다 (sample = false). 올해 = 그 품목 마지막 거래일의 해
     */
    private static final double THIN = 0.02;

    public Map<String, Object> monthly(String item, String variety, List<Integer> unitIds) {
        LocalDate last = unitIds != null
                ? date(db.rows("SELECT max(date) AS b FROM price_unit_daily WHERE unit_id IN (:u)", p("u", unitIds)).get(0).get("b"))
                : date(db.rows("SELECT max(date) AS b FROM price_daily WHERE item_code = :i AND market_code = 'national' AND grade = 'ALL'", p("i", item)).get(0).get("b"));
        if (last == null) throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.NOT_FOUND, "이 품목의 시세가 DB 에 없습니다: " + item);
        int year = last.getYear(), cur = last.getMonthValue();
        LocalDate from = LocalDate.of(year - 5, 1, 1);
        List<Map<String, Object>> rows = unitIds != null
                ? db.rows("SELECT extract(year FROM date)::int AS y, extract(month FROM date)::int AS m, sum(amount_won) AS a, sum(volume_kg) AS v "
                        + "FROM price_unit_daily WHERE unit_id IN (:u) AND date BETWEEN :a AND :b GROUP BY 1, 2", p("u", unitIds, "a", from, "b", last))
                : db.rows("SELECT extract(year FROM date)::int AS y, extract(month FROM date)::int AS m, sum(amount_won) AS a, sum(volume_kg) AS v "
                        + "FROM price_daily WHERE item_code = :i AND market_code = 'national' AND grade = 'ALL' AND date BETWEEN :a AND :b GROUP BY 1, 2",
                        p("i", item, "a", from, "b", last));
        double[] nP = new double[13], nV = new double[13];
        int[] nPc = new int[13], nVc = new int[13];
        Integer[] aP = new Integer[12], fP = new Integer[12];
        Double[] aV = new Double[12];
        for (Map<String, Object> r : rows) {
            int y = num(r.get("y")).intValue(), m = num(r.get("m")).intValue();
            Double a = num(r.get("a")), v = num(r.get("v"));
            if (v == null || v <= 0) continue;
            if (y == year) {
                aV[m - 1] = ton(v);
                if (a != null) aP[m - 1] = (int) Math.round(a / v);
            } else {
                nV[m] += v / 1000; nVc[m]++;
                if (a != null) { nP[m] += a / v; nPc[m]++; }
            }
        }
        // 물량이 가장 많은 달의 2% 도 안 되는 달은 몇 kg 거래로 값이 튀어서 가격을 비움 (철 밖 달, 11-13)
        double nMax = 0, aMax = 0;
        for (int m = 1; m <= 12; m++) {
            if (nVc[m] > 0) nMax = Math.max(nMax, nV[m] / nVc[m]);
            if (aV[m - 1] != null) aMax = Math.max(aMax, aV[m - 1]);
        }
        for (int m = 0; m < cur - 1; m++) if (aV[m] != null && aV[m] < aMax * THIN) aP[m] = null; // 이번 달은 아직 덜 차서 빼고
        List<Integer> normal = new ArrayList<>();
        List<Double> vNormal = new ArrayList<>();
        for (int m = 1; m <= 12; m++) {
            normal.add(nPc[m] > 0 && nV[m] / nVc[m] >= nMax * THIN ? (int) Math.round(nP[m] / nPc[m]) : null);
            vNormal.add(nVc[m] > 0 ? round1(nV[m] / nVc[m]) : null);
        }
        // 예측: 오늘 이전에 만든 가장 최근 기준일의 예측 표. 표가 없는 DB(예전 판)면 예측 없이
        String vid = variety == null || variety.isBlank() ? "ALL" : variety;
        try {
            for (Map<String, Object> r : db.rows("SELECT extract(month FROM target_date)::int AS m, avg(price) AS p FROM price_forecast_daily "
                    + "WHERE item_code = :i AND variety_id = :v AND base_date = (SELECT max(base_date) FROM price_forecast_daily WHERE item_code = :i AND variety_id = :v AND base_date <= :t) "
                    + "AND extract(year FROM target_date) = :y AND extract(month FROM target_date) > :c GROUP BY 1", p("i", item, "v", vid, "t", LocalDate.now(), "y", year, "c", cur))) {
                fP[num(r.get("m")).intValue() - 1] = won(r.get("p"));
            }
        } catch (RuntimeException e) {
            // price_forecast_daily 가 없으면 예측 칸은 비움
        }
        fP[cur - 1] = aP[cur - 1]; // 예측 점선은 이번 달 실제 점에서 시작
        boolean anyForecast = false;
        for (int m = cur; m < 12; m++) anyForecast |= fP[m] != null;
        List<Integer> actual = new ArrayList<>(), forecast = new ArrayList<>();
        List<Double> vActual = new ArrayList<>();
        for (int m = 0; m < 12; m++) {
            actual.add(m < cur ? aP[m] : null);
            vActual.add(m < cur ? aV[m] : null);
            forecast.add(m >= cur - 1 && anyForecast && (m == cur - 1 || normal.get(m) != null) ? fP[m] : null); // 평년 가격이 빈 달(철 밖)은 예측도 비움
        }
        return obj("item", item, "variety", vid, "year", year, "current_month", cur, "last_date", iso(last), "normal_years", List.of(year - 5, year - 1),
                "price", obj("normal", normal, "actual", actual, "forecast", forecast),
                "volume", obj("normal", vNormal, "actual", vActual, "partial_month", last.lengthOfMonth() == last.getDayOfMonth() ? null : cur),
                "source", "공영도매시장 경매원장 " + (year - 5) + "~" + year + " 월별 · 예측 = 일 단위 예측 표", "sample", false);
    }
}
