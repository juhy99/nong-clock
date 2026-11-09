package com.farm.backend.controller;

import com.farm.backend.service.PriceService;
import com.farm.backend.service.VarietyCatalog;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
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

    private Integer unit(String variety, String market) {
        if (variety == null || variety.isBlank() || !"national".equals(market)) return null;
        String name = varieties.unitName(variety);
        Integer id = name == null ? null : prices.unitIdOf(name);
        if (id == null) throw new ResponseStatusException(HttpStatus.NOT_FOUND, "품종 " + variety + " 의 시세가 DB 에 없습니다");
        return id;
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
        return prices.grades(item, market, day(date), unit(variety, market));
    }

    @GetMapping("/prices/{item}/history")
    public Map<String, Object> history(@PathVariable String item, @RequestParam(defaultValue = "national") String market,
                                       @RequestParam(defaultValue = "HIGH") String grade, @RequestParam(required = false) String date,
                                       @RequestParam(defaultValue = "8") int days, @RequestParam(required = false) String variety) {
        if (!GRADE_SET.contains(grade)) throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "grade 는 " + PriceService.GRADES + " 중 하나");
        return prices.history(item, market, grade, day(date), Math.max(1, Math.min(days, 400)), unit(variety, market));
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
}
