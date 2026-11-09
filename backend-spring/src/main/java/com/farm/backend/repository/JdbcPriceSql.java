package com.farm.backend.repository;

import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** 시세 표는 JPA 엔티티 없이 SQL 로 읽는다 (ddl-auto: validate 와 무관, 표는 팀 수집기 farmbid_daily 가 만든다) */
@Component
public class JdbcPriceSql implements PriceSql {
    private final NamedParameterJdbcTemplate jdbc;

    public JdbcPriceSql(NamedParameterJdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public List<Map<String, Object>> rows(String sql, Map<String, ?> params) {
        return jdbc.queryForList(sql, params);
    }
}
