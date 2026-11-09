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
    /** upto(없으면 최근) 이전의 거래일 n개, 오래된 → 최근. 그 품목·시장(또는 품종)에 거래가 있던 날만 */
    List<LocalDate> tradeDates(String item, String market, LocalDate upto, int n, Integer unitId) {
        String cond = upto == null ? "" : " AND date <= :d";
        List<Map<String, Object>> rows = unitId != null
                ? db.rows("SELECT DISTINCT date FROM price_unit_daily WHERE unit_id = :u" + cond + " ORDER BY date DESC LIMIT :n",
                        p("u", unitId, "d", upto, "n", n))
                : db.rows("SELECT DISTINCT date FROM price_daily WHERE item_code = :i AND market_code = :m" + cond + " ORDER BY date DESC LIMIT :n",
                        p("i", item, "m", market, "d", upto, "n", n));
        return rows.stream().map(r -> date(r.get("date"))).sorted().collect(Collectors.toList());
    }

    public Integer unitIdOf(String unitName) {
        if (unitName == null) return null;
        List<Map<String, Object>> r = db.rows("SELECT unit_id FROM variety_unit WHERE unit_name = :n", p("n", unitName));
        return r.isEmpty() ? null : num(r.get(0).get("unit_id")).intValue();
    }

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

    public Map<String, Object> grades(String item, String market, LocalDate date, Integer unitId) {
        List<LocalDate> days = tradeDates(item, market, date, 5, unitId);
        if (days.isEmpty())
            return obj("item", item, "market", market, "base_date", null, "compared_date", null, "unit", "kg", "grades", List.of(), "retail", emptyRetail(days));
        LocalDate base = days.get(days.size() - 1), prev = days.size() > 1 ? days.get(days.size() - 2) : null;
        LocalDate yaLo = base.minusDays(394), yaHi = base.minusDays(364);
        List<Map<String, Object>> grades = new ArrayList<>();
        if (unitId != null) {   // 품종: 등급 구분이 없는 표 → 평균(ALL) 카드 하나
            Map<LocalDate, Integer> s = new HashMap<>();
            for (Map<String, Object> r : db.rows("SELECT date, price FROM price_unit_daily WHERE unit_id = :u AND date IN (:ds)", p("u", unitId, "ds", days)))
                s.put(date(r.get("date")), won(r.get("price")));
            List<Map<String, Object>> ya = db.rows("SELECT price FROM price_unit_daily WHERE unit_id = :u AND date BETWEEN :a AND :b ORDER BY date DESC LIMIT 1",
                    p("u", unitId, "a", yaLo, "b", yaHi));
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
        if (unitId == null)
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
    public Map<String, Object> history(String item, String market, String grade, LocalDate date, int days, Integer unitId) {
        List<LocalDate> ds = tradeDates(item, market, date, days + 1, unitId);
        Map<LocalDate, Integer[]> pr = new HashMap<>();   // [가격, 최고, 최저]
        Map<LocalDate, Object> vol = new HashMap<>();
        if (!ds.isEmpty()) {
            if (unitId != null) {
                for (Map<String, Object> r : db.rows("SELECT date, price, volume_kg FROM price_unit_daily WHERE unit_id = :u AND date IN (:ds)",
                        p("u", unitId, "ds", ds))) {
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
        return obj("item", item, "market", market, "grade", unitId != null ? "ALL" : grade, "unit", "kg", "points", pts);
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
}
