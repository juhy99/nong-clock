package com.farm.backend.controller;

import com.farm.backend.service.PriceService;
import com.farm.backend.service.VarietyCatalog;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/** 11-17: 다른 품목의 품종은 404, 오류는 {"message","detail"} 모양 */
class PriceControllerTest {
    private PriceService prices;
    private VarietyCatalog varieties;
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        prices = mock(PriceService.class);
        varieties = mock(VarietyCatalog.class);
        mvc = MockMvcBuilders.standaloneSetup(new PriceController(prices, varieties)).build();
    }

    @Test
    void varietyOfAnotherItemIs404WithMessage() throws Exception {
        mvc.perform(get("/api/prices/apple/history").param("variety", "pear-1"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("품종 pear-1 은(는) apple 의 품종이 아닙니다"))
                .andExpect(jsonPath("$.detail").value("품종 pear-1 은(는) apple 의 품종이 아닙니다"));
        verify(prices, never()).history(any(), any(), any(), any(), anyInt(), any());
    }

    @Test
    void varietyWithoutDbRowsKeepsReasonInBody() throws Exception {
        when(varieties.unitNames("apple-99")).thenReturn(List.of("없는단위"));
        when(prices.unitIdsOf(List.of("없는단위"))).thenReturn(List.of());
        mvc.perform(get("/api/prices/apple/monthly").param("variety", "apple-99"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("품종 apple-99 의 시세가 DB 에 없습니다"));
    }

    @Test
    void ownVarietyStillWorks() throws Exception {
        when(varieties.unitNames("apple-2")).thenReturn(List.of("u"));
        when(prices.unitIdsOf(List.of("u"))).thenReturn(List.of(7));
        when(prices.history(eq("apple"), eq("national"), eq("HIGH"), isNull(), eq(8), eq(List.of(7)))).thenReturn(Map.of("item", "apple"));
        mvc.perform(get("/api/prices/apple/history").param("variety", "apple-2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.item").value("apple"));
    }

    @Test
    void textInNumberParamIs400WithMessage() throws Exception {
        mvc.perform(get("/api/prices/apple/history").param("days", "abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("요청 값을 확인하세요 (days)"));
    }
}
