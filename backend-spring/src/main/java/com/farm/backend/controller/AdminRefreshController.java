package com.farm.backend.controller;

import com.farm.backend.config.ApiException;
import com.farm.backend.service.UpdaterService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.Map;

/**
 * 관리자 데이터 갱신 (11-17) — 갱신 서비스(price-updater)에 전달만 한다. /api/admin/** 는 SecurityConfig 가 관리자 로그인만 통과시킴
 *   GET  /api/admin/refresh            상태: 예측 기준일 · v4 기준월 · 자료별 수집 결과 · 월보 · 실행 중 · 최근 실행
 *   POST /api/admin/refresh/daily      지금 갱신 (수집 → 표 → DB → 예측). 바로 202, 진행은 상태로 확인
 *   POST /api/admin/refresh/monthly    월 예측(v4) 만들기 → 매일 갱신까지
 *   POST /api/admin/refresh/wolbo      월보 PDF 올리기 (multipart file)
 */
@RestController
@RequestMapping("/api/admin/refresh")
public class AdminRefreshController {
    private final UpdaterService updater;

    public AdminRefreshController(UpdaterService updater) {
        this.updater = updater;
    }

    @GetMapping
    public Map<String, Object> status() {
        return updater.status();
    }

    @PostMapping("/wolbo")
    public ResponseEntity<Map<String, Object>> wolbo(@RequestParam("file") MultipartFile file) throws IOException {
        if (file == null || file.isEmpty()) throw new ApiException(HttpStatus.BAD_REQUEST, "빈 파일이에요");
        if (file.getSize() > UpdaterService.WOLBO_MAX) throw new ApiException(HttpStatus.PAYLOAD_TOO_LARGE, "파일이 너무 커요 (50MB 까지)");
        return ResponseEntity.status(HttpStatus.CREATED).body(updater.uploadWolbo(file.getOriginalFilename(), file.getBytes()));
    }

    @PostMapping("/{job}")
    public ResponseEntity<Map<String, Object>> run(@PathVariable String job) {
        return ResponseEntity.accepted().body(updater.run(job));
    }
}
