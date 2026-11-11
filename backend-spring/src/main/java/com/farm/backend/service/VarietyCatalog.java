package com.farm.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 화면의 품종 id(apple-2) → 예측 단위 이름 목록(["사과 홍로"]). 목록은 저장소 shared/items50.json 한 파일 (화면·ml-api 와 같이 씀).
 * 품종 하나에 예측 단위가 여럿일 수 있다 (11-11: 화면묶음째 품종, 예: 양파 기타 = 양파(기타·봄 전남) 외 3개) → 시세는 그 단위들을 합쳐서 계산.
 * 위치: 설정 shared.dir (도커 compose 는 /app/shared 로 붙임, 내 PC 에서 backend-spring 폴더로 실행하면 ../shared)
 */
@Component
public class VarietyCatalog {
    private final Path file;
    private Map<String, List<String>> units;

    public VarietyCatalog(@Value("${shared.dir:../shared}") String dir) {
        this.file = Path.of(dir, "items50.json");
    }

    /** 품종 id 의 예측 단위 이름들. 모르는 id 면 null */
    public synchronized List<String> unitNames(String varietyId) {
        if (varietyId == null || varietyId.isBlank()) return null;
        if (units == null) {
            Map<String, List<String>> m = new HashMap<>();
            try {
                JsonNode root = new ObjectMapper().readTree(Files.readString(file));
                for (JsonNode it : root.path("items"))
                    for (JsonNode v : it.path("varieties")) {
                        List<String> names = new ArrayList<>();
                        for (JsonNode u : v.path("units")) names.add(u.asText());
                        if (names.isEmpty() && v.hasNonNull("unit")) names.add(v.path("unit").asText());   // 예전 파일 모양 (unit 하나)
                        m.put(v.path("id").asText(), List.copyOf(names));
                    }
            } catch (Exception e) {
                throw new IllegalStateException("품종 목록을 읽을 수 없습니다: " + file.toAbsolutePath(), e);
            }
            units = m;
        }
        return units.get(varietyId);
    }
}
