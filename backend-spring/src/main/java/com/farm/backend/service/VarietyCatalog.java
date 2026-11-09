package com.farm.backend.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

/**
 * 화면의 품종 id(apple-2) → 예측 단위 이름(사과 홍로). 목록은 저장소 shared/items50.json 한 파일 (화면·ml-api 와 같이 씀).
 * 위치: 설정 shared.dir (도커 compose 는 /app/shared 로 붙임, 내 PC 에서 backend-spring 폴더로 실행하면 ../shared)
 */
@Component
public class VarietyCatalog {
    private final Path file;
    private Map<String, String> units;

    public VarietyCatalog(@Value("${shared.dir:../shared}") String dir) {
        this.file = Path.of(dir, "items50.json");
    }

    public synchronized String unitName(String varietyId) {
        if (varietyId == null || varietyId.isBlank()) return null;
        if (units == null) {
            Map<String, String> m = new HashMap<>();
            try {
                JsonNode root = new ObjectMapper().readTree(Files.readString(file));
                for (JsonNode it : root.path("items"))
                    for (JsonNode v : it.path("varieties")) m.put(v.path("id").asText(), v.path("unit").asText());
            } catch (Exception e) {
                throw new IllegalStateException("품종 목록을 읽을 수 없습니다: " + file.toAbsolutePath(), e);
            }
            units = m;
        }
        return units.get(varietyId);
    }
}
