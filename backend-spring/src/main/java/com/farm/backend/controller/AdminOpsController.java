package com.farm.backend.controller;

import com.farm.backend.config.OpsLog;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.sql.Date;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;

/**
 * 관리자 운영 화면 (11-17) — 관리자 로그인(ROLE_ADMIN)만 (SecurityConfig /api/admin/**). 모두 읽기만 함.
 *   GET /api/admin/ops/freshness           자료가 며칠 것까지 들어왔나 (시세 · 품종 시세 · 소매가 · 예측 기준일 · 월 예측 기준월)
 *   GET /api/admin/ops/forecast-health     가장 최근 예측 표 점검: 하루 사이 크게 바뀌는 곳 · 지금 가격과 크게 다른 품목 · 거래가 오래된 품목 · 앞 판과 달라진 정도
 *   GET /api/admin/ops/forecast-vs-actual  지난 예측과 그 뒤 실제 경매 단가 비교 (품목 전체 · 전국)
 *   GET /api/admin/ops/errors              서버 오류 · 요청 제한 · 로그인 실패 기록 (메모리, OpsLog)
 *   GET /api/admin/ops/flood               짧은 시간에 글·댓글을 많이 쓴 회원 (도배 감지)
 * 예측·시세 표(price_…)는 수집기가 만드는 표라 없을 수도 있음 → 없으면 그 칸만 null
 */
@RestController
@RequestMapping("/api/admin/ops")
public class AdminOpsController {
    /** 하루 사이 이만큼 넘게 바뀌면 목록에 (사용자 예측 화면의 🔀 안내와 같은 기준) */
    static final double STEP_RATIO = 1.25;
    /** 30일 안 예측이 지금 가격의 이 배수를 넘거나 1/배수 밑이면 '지금 가격과 크게 다름' */
    static final double FAR_RATIO = 4.0;
    static final int STALE_DAYS = 7;
    static final int FLOOD_HOUR = 5, FLOOD_DAY = 30;

    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(AdminOpsController.class);
    private final NamedParameterJdbcTemplate jdbc;
    private final OpsLog opsLog;

    public AdminOpsController(NamedParameterJdbcTemplate jdbc, OpsLog opsLog) {
        this.jdbc = jdbc;
        this.opsLog = opsLog;
    }

    private List<Map<String, Object>> rows(String sql, Map<String, ?> params) {
        List<Map<String, Object>> out = jdbc.queryForList(sql, new MapSqlParameterSource(params));
        for (Map<String, Object> r : out)   // 날짜·시각은 글자로 (JSON 모양을 한 가지로)
            r.replaceAll((k, v) -> v instanceof Date d ? d.toLocalDate().toString() : v instanceof Timestamp t ? t.toLocalDateTime().toString() : v);
        return out;
    }

    /** 표가 없거나 비어 있으면 null */
    private Object one(String sql) {
        try {
            List<Map<String, Object>> r = rows(sql, Map.of());
            return r.isEmpty() ? null : r.get(0).values().iterator().next();
        } catch (Exception e) {
            return null;
        }
    }

    @GetMapping("/freshness")
    public Map<String, Object> freshness() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("today", LocalDate.now().toString());
        m.put("price_last", one("SELECT max(date) FROM price_daily"));
        m.put("unit_last", one("SELECT max(date) FROM price_unit_daily"));
        m.put("retail_last", one("SELECT max(date) FROM retail_price_daily"));
        m.put("forecast_base", one("SELECT max(base_date) FROM price_forecast_daily"));
        m.put("forecast_end", one("SELECT max(target_date) FROM price_forecast_daily WHERE base_date = (SELECT max(base_date) FROM price_forecast_daily)"));
        m.put("monthly_base", one("SELECT max(base_month) FROM price_forecast_monthly"));
        return m;
    }

    static final String BASES_SQL = """
            SELECT base_date, count(*) AS rows, count(DISTINCT item_code || '/' || variety_id) AS series,
                   sum(off_season) AS off_rows, sum(crash_adj) AS crash_rows, min(target_date) AS first_date, max(target_date) AS last_date
            FROM price_forecast_daily GROUP BY base_date ORDER BY base_date DESC LIMIT 8""";
    static final String STEPS_SQL = """
            WITH f AS (
              SELECT item_code, variety_id, target_date, price, model,
                     lag(price) OVER w AS prev_price, lag(target_date) OVER w AS prev_date
              FROM price_forecast_daily WHERE base_date = :b
              WINDOW w AS (PARTITION BY item_code, variety_id ORDER BY target_date))
            SELECT f.item_code, i.name AS item_name, f.variety_id, f.prev_date, f.target_date, f.prev_price, f.price, f.model,
                   round((f.price::numeric / f.prev_price - 1) * 100, 1) AS change_pct,
                   count(*) OVER () AS total
            FROM f JOIN item i ON i.item_code = f.item_code
            WHERE f.prev_price > 0 AND f.target_date - f.prev_date <= 3
              AND (f.price >= f.prev_price * :r OR f.price * :r <= f.prev_price)
            ORDER BY abs(ln(f.price::float / f.prev_price)) DESC, f.item_code, f.target_date LIMIT 150""";
    static final String ITEMS_SQL = """
            WITH lt AS (
              SELECT item_code, max(date) AS d FROM price_daily
              WHERE market_code = 'national' AND grade = 'ALL' AND date <= :b AND date > :b - 400 GROUP BY item_code),
            bp AS (
              SELECT p.item_code, lt.d AS last_trade,
                     round(COALESCE(sum(p.amount_won) / NULLIF(sum(CASE WHEN p.amount_won IS NOT NULL THEN p.volume_kg END), 0), avg(p.price))) AS base_price
              FROM price_daily p JOIN lt ON lt.item_code = p.item_code AND p.date > lt.d - 7 AND p.date <= lt.d
              WHERE p.market_code = 'national' AND p.grade = 'ALL' GROUP BY p.item_code, lt.d),
            fx AS (
              SELECT item_code, max(price) AS max_30, min(price) AS min_30, count(*) AS days_30, min(target_date) AS first_date
              FROM price_forecast_daily WHERE base_date = :b AND variety_id = 'ALL' AND target_date <= :b + 30 GROUP BY item_code),
            fa AS (
              SELECT item_code, count(*) AS days_all, count(DISTINCT variety_id) - 1 AS varieties
              FROM price_forecast_daily WHERE base_date = :b GROUP BY item_code)
            SELECT i.item_code, i.name AS item_name, bp.last_trade, bp.base_price, fx.max_30, fx.min_30, COALESCE(fx.days_30, 0) AS days_30,
                   fx.first_date, fa.days_all, fa.varieties
            FROM fa JOIN item i ON i.item_code = fa.item_code LEFT JOIN bp ON bp.item_code = i.item_code LEFT JOIN fx ON fx.item_code = i.item_code
            ORDER BY i.sort_order NULLS LAST, i.item_code""";
    static final String DIFF_SQL = """
            SELECT a.item_code, i.name AS item_name, count(*) AS days,
                   round(avg(abs(a.price::numeric / b.price - 1)) * 100, 1) AS mean_change_pct,
                   round(max(abs(a.price::numeric / b.price - 1)) * 100, 1) AS max_change_pct
            FROM price_forecast_daily a
            JOIN price_forecast_daily b ON b.base_date = :prev AND b.item_code = a.item_code AND b.variety_id = a.variety_id AND b.target_date = a.target_date
            JOIN item i ON i.item_code = a.item_code
            WHERE a.base_date = :b AND a.variety_id = 'ALL' AND b.price > 0
            GROUP BY a.item_code, i.name ORDER BY mean_change_pct DESC""";

    @GetMapping("/forecast-health")
    public Map<String, Object> forecastHealth() {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("step_ratio", STEP_RATIO);
        out.put("far_ratio", FAR_RATIO);
        out.put("stale_days", STALE_DAYS);
        List<Map<String, Object>> bases;
        try {
            bases = rows(BASES_SQL, Map.of());
        } catch (Exception e) {
            bases = List.of();
        }
        out.put("bases", bases);
        if (bases.isEmpty()) return out;
        LocalDate b = LocalDate.parse((String) bases.get(0).get("base_date"));
        List<Map<String, Object>> steps = rows(STEPS_SQL, Map.of("b", b, "r", STEP_RATIO));
        out.put("steps_total", steps.isEmpty() ? 0 : ((Number) steps.get(0).get("total")).longValue());
        steps.forEach(r -> r.remove("total"));
        out.put("steps", steps);
        List<Map<String, Object>> items = rows(ITEMS_SQL, Map.of("b", b));
        for (Map<String, Object> r : items) {
            List<String> flags = new ArrayList<>();
            Number base = (Number) r.get("base_price"), mx = (Number) r.get("max_30"), mn = (Number) r.get("min_30");
            String last = (String) r.get("last_trade");
            boolean stale = last == null || LocalDate.parse(last).isBefore(b.minusDays(STALE_DAYS));
            if (((Number) r.get("days_30")).intValue() == 0) flags.add("no_30");          // 30일 안 예측 없음 (출하철 밖이면 정상)
            else {
                if (stale) flags.add("stale");                                               // 거래가 오래됐는데 예측은 있음
                if (base != null && base.doubleValue() > 0 && mx != null
                        && (mx.doubleValue() / base.doubleValue() > FAR_RATIO || mn.doubleValue() / base.doubleValue() < 1 / FAR_RATIO)) flags.add("far");
            }
            r.put("flags", flags);
        }
        out.put("items", items);
        if (bases.size() > 1) {
            LocalDate prev = LocalDate.parse((String) bases.get(1).get("base_date"));
            out.put("prev_base", prev.toString());
            out.put("diff", rows(DIFF_SQL, Map.of("b", b, "prev", prev)));
        }
        return out;
    }

    /** 예측(품목 전체)과 그 목표일의 실제 전국 경매 단가(평균 등급 = 금액 ÷ 물량). 거리 = 목표일 − 기준일 (달력 일) */
    static final String VS_FROM = """
            FROM price_forecast_daily f
            JOIN price_daily p ON p.date = f.target_date AND p.item_code = f.item_code AND p.market_code = 'national' AND p.grade = 'ALL'
            JOIN item i ON i.item_code = f.item_code
            WHERE f.variety_id = 'ALL' AND p.price > 0 AND f.off_season = 0""";   // 참고값(월 예측이 끝난 뒤 · 출하철 밖)은 견주지 않음
    static final String VS_AGG = "count(*) AS n, round(avg(abs(f.price::numeric / p.price - 1)) * 100, 1) AS error_pct, round(avg(f.price::numeric / p.price - 1) * 100, 1) AS bias_pct";

    @GetMapping("/forecast-vs-actual")
    public Map<String, Object> forecastVsActual() {
        Map<String, Object> out = new LinkedHashMap<>();
        try {
            out.put("total", rows("SELECT " + VS_AGG + ", min(f.target_date) AS first_date, max(f.target_date) AS last_date, count(DISTINCT f.base_date) AS bases " + VS_FROM, Map.of()).get(0));
            out.put("by_distance", rows("SELECT CASE WHEN f.target_date - f.base_date <= 7 THEN '1~7일' WHEN f.target_date - f.base_date <= 20 THEN '8~20일' ELSE '21일~' END AS distance, "
                    + VS_AGG + " " + VS_FROM + " GROUP BY 1 ORDER BY min(f.target_date - f.base_date)", Map.of()));
            out.put("by_base", rows("SELECT f.base_date, " + VS_AGG + " " + VS_FROM + " GROUP BY f.base_date ORDER BY f.base_date DESC LIMIT 30", Map.of()));
            out.put("by_item", rows("SELECT f.item_code, i.name AS item_name, " + VS_AGG + " " + VS_FROM + " GROUP BY f.item_code, i.name ORDER BY error_pct DESC", Map.of()));
            out.put("recent", rows("SELECT f.base_date, f.target_date, f.item_code, i.name AS item_name, f.price AS predicted, p.price AS actual, "
                    + "round((f.price::numeric / p.price - 1) * 100, 1) AS diff_pct, round(p.volume_kg / 1000) AS volume_t " + VS_FROM
                    + " AND f.base_date = (SELECT max(f2.base_date) FROM price_forecast_daily f2 WHERE f2.base_date < (SELECT max(date) FROM price_daily)) "
                    + "ORDER BY f.target_date DESC, abs(f.price::numeric / p.price - 1) DESC LIMIT 200", Map.of()));
        } catch (org.springframework.dao.DataAccessException e) {   // 표가 없는 DB (수집 전)
            log.warn("예측·실제 비교 실패: {}", e.getMostSpecificCause().getMessage());
            out.put("error", "예측 표나 시세 표가 아직 없어요");
        }
        return out;
    }

    @GetMapping("/errors")
    public Map<String, Object> errors() {
        return opsLog.snapshot();
    }

    static final String FLOOD_SQL = """
            SELECT * FROM (
              SELECT u.user_id AS id, u.name AS nickname, u.email,
                (SELECT count(*) FROM post p WHERE p.author_id = u.user_id AND p.created_at > :h) + (SELECT count(*) FROM post_comment c WHERE c.author_id = u.user_id AND c.created_at > :h) AS last_hour,
                (SELECT count(*) FROM post p WHERE p.author_id = u.user_id AND p.created_at > :d) + (SELECT count(*) FROM post_comment c WHERE c.author_id = u.user_id AND c.created_at > :d) AS last_day
              FROM users u) x
            WHERE x.last_hour >= :nh OR x.last_day >= :nd ORDER BY x.last_hour DESC, x.last_day DESC LIMIT 30""";

    /** 글·댓글 작성 시각은 서버(JVM) 시각으로 저장되므로 기준 시각도 서버 시각으로 */
    @GetMapping("/flood")
    public Map<String, Object> flood() {
        LocalDateTime now = LocalDateTime.now();
        return Map.of("hour_limit", FLOOD_HOUR, "day_limit", FLOOD_DAY,
                "rows", rows(FLOOD_SQL, Map.of("h", now.minusHours(1), "d", now.minusDays(1), "nh", FLOOD_HOUR, "nd", FLOOD_DAY)));
    }
}
