package com.farm.backend.controller;

import com.farm.backend.service.PriceService;
import com.farm.backend.service.VarietyCatalog;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.server.ResponseStatusException;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 시세·수급 API — docs/06_api_spec.md 2-1 · 2-15 (2026-11-09).
 * 화면: frontend/src/api/market.js (frontend/.env 의 VITE_PRICE_SOURCE=db 일 때 이 주소를 부름. 서버는 nginx 가 /api → backend)
 * 공통: market 생략 = national(전국 평균), date 생략 = 최근 거래일 (거래 없는 날을 주면 그 전 가장 가까운 거래일), grade 생략 = HIGH
 * 품종: ?variety=apple-2 (shared/items50.json 의 id). 품종 표는 전국만 있어서 시장을 고르면 품목 전체 값을 준다.
 */
@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:5173")
public class PriceController {
    private static final Set<String> GRADE_SET = Set.copyOf(PriceService.GRADES);

    private final PriceService prices;
    private final VarietyCatalog varieties;

    public PriceController(PriceService prices, VarietyCatalog varieties) {
        this.prices = prices;
        this.varieties = varieties;
    }

    private static LocalDate day(String s) {
        if (s == null || s.isBlank()) return null;
        try {
            return LocalDate.parse(s);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "date 는 YYYY-MM-DD 로 주세요: " + s);
        }
    }

    /**
     * 품종의 예측 단위 id 들 (품종 하나 = 단위 하나 또는 화면묶음째 여럿). 품종을 안 골랐거나 시장을 골랐으면 null = 품목 전체.
     * 11-17: 다른 품목의 품종(예: /prices/apple/...?variety=pear-1)이면 404 — 예전에는 배 값을 사과 이름으로 돌려줬음
     */
    private List<Integer> units(String item, String variety, String market) {
        if (variety == null || variety.isBlank()) return null;
        if (!variety.startsWith(item + "-")) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "품종 " + variety + " 은(는) " + item + " 의 품종이 아닙니다");
        if (!"national".equals(market)) return null;
        List<Integer> ids = prices.unitIdsOf(varieties.unitNames(variety));
        if (ids.isEmpty()) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "품종 " + variety + " 의 시세가 DB 에 없습니다");
        return ids;
    }

    @GetMapping("/prices/today")
    public Map<String, Object> today() {
        return prices.today();
    }

    @GetMapping("/markets")
    public List<Map<String, Object>> markets() {
        return prices.markets();
    }

    @GetMapping("/prices/{item}/grades")
    public Map<String, Object> grades(@PathVariable String item, @RequestParam(defaultValue = "national") String market,
                                      @RequestParam(required = false) String date, @RequestParam(required = false) String variety) {
        return prices.grades(item, market, day(date), units(item, variety, market));
    }

    @GetMapping("/prices/{item}/history")
    public Map<String, Object> history(@PathVariable String item, @RequestParam(defaultValue = "national") String market,
                                       @RequestParam(defaultValue = "HIGH") String grade, @RequestParam(required = false) String date,
                                       @RequestParam(defaultValue = "8") int days, @RequestParam(required = false) String variety) {
        if (!GRADE_SET.contains(grade)) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "grade 는 " + PriceService.GRADES + " 중 하나");
        return prices.history(item, market, grade, day(date), Math.max(1, Math.min(days, 400)), units(item, variety, market));
    }

    @GetMapping("/prices/{item}/origins")
    public Map<String, Object> origins(@PathVariable String item, @RequestParam(defaultValue = "national") String market,
                                       @RequestParam(required = false) String date) {
        return prices.origins(item, market, day(date));
    }

    @GetMapping("/volumes/{item}")
    public Map<String, Object> volumes(@PathVariable String item, @RequestParam(defaultValue = "national") String market,
                                       @RequestParam(required = false) String date, @RequestParam(defaultValue = "9") int periods) {
        return prices.volumes(item, market, day(date), Math.max(2, Math.min(periods, 36)));
    }

    @GetMapping("/prices/{item}/markets")
    public Map<String, Object> compare(@PathVariable String item) {
        return prices.compare(item);
    }

    /** 도매시장별 최근 12달 평균 경락가 · 물량 몫 (시세 화면 맨 아래, 11-12). 품종을 주면 그 품종 (시장 × 품종 월 표) */
    @GetMapping("/prices/{item}/market-share")
    public Map<String, Object> marketShare(@PathVariable String item, @RequestParam(required = false) String variety) {
        return prices.marketShare(item, units(item, variety, "national"));
    }

    /** 산지공판장 최근 12달 · 23~25년 평균 경락가 · 물량 몫 (시세 화면 맨 아래, 11-12). 품종별 산지 자료가 없어 품목 값 */
    @GetMapping("/prices/{item}/auction-houses")
    public Map<String, Object> auctionHouses(@PathVariable String item, @RequestParam(required = false) String variety) {
        return prices.auctionHouses(item);
    }

    /** 가격 예측 화면의 계절 패턴 · 월별 반입량 (11-13): 평년 · 올해 실제 · 남은 달 예측. 품종을 주면 그 품종 */
    @GetMapping("/prices/{item}/monthly")
    public Map<String, Object> monthly(@PathVariable String item, @RequestParam(required = false) String variety) {
        return prices.monthly(item, variety, units(item, variety, "national"));
    }

    /**
     * 오류도 화면이 읽는 {"message","detail"} 로 (11-17). 예전에는 스프링 기본 오류 모양(timestamp·status·error)이라
     * 화면에 "HTTP 404" 만 보이고 "품종 … 시세가 DB 에 없습니다" 같은 이유가 사라졌음
     */
    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> failed(ResponseStatusException e) {
        String why = e.getReason() == null ? "시세를 불러오지 못했어요" : e.getReason();
        return ResponseEntity.status(e.getStatusCode()).body(Map.of("message", why, "detail", why));
    }

    /** ?days=abc 처럼 숫자 칸에 글자 → 400 */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<Map<String, Object>> typeMismatch(MethodArgumentTypeMismatchException e) {
        String why = "요청 값을 확인하세요 (" + e.getName() + ")";
        return ResponseEntity.badRequest().body(Map.of("message", why, "detail", why));
    }
}
