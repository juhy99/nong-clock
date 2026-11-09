package com.farm.backend.repository;

import java.util.List;
import java.util.Map;

/** SELECT 한 번 → [{열: 값}]. 운영은 JdbcPriceSql(NamedParameterJdbcTemplate), 시험 때는 가짜로 바꿔 끼운다. 파라미터는 :이름 */
public interface PriceSql {
    List<Map<String, Object>> rows(String sql, Map<String, ?> params);
}
