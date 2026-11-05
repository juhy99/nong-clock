// 홈 지수 카드 가짜 데이터 (Spring 담당 API 가 생기기 전까지 사용). 응답 모양은 docs/06_api_spec.md 2-16 과 같다.
// 지수 = 품목마다 평소 가격(최근 60거래일 평균)을 100 으로 놓고, 날마다 "전날·당일 둘 다 거래된 품목"의
// 오른 비율을 평균내 이어 붙인 값 (품목 수가 바뀌는 날에도 튀지 않게). 가격 = 전국 도매시장 · 상 등급
import CATALOG from "../../../shared/items.json";
import { ITEMS } from "./catalog";
import { mockPriceHistory } from "./market";

export const INDEX_GROUPS = [
  { code: "all", name: "전체", emoji: "📊", categories: null },
  ...CATALOG.index_groups,
];
const BASE_DAYS = 60;
const r1 = (v) => Math.round(v * 10) / 10;

/** 묶음별 지수 최근 days 거래일 */
export function mockMarketIndex({ days = 30 } = {}) {
  const series = ITEMS.map((i) => ({ ...i, points: mockPriceHistory(i.code, { days: BASE_DAYS }).points }));
  const dates = series[0].points.slice(-days).map((p) => p.date);
  const groups = INDEX_GROUPS.map((g) => {
    const members = series.filter((s) => !g.categories || g.categories.includes(s.category));
    const rows = members.map((s) => {
      const prices = s.points.map((p) => p.price).filter((v) => v != null);
      const base = prices.reduce((a, b) => a + b, 0) / prices.length;
      return { base, byDate: Object.fromEntries(s.points.map((p) => [p.date, p.price])) };
    });
    const first = rows.filter((r) => r.byDate[dates[0]] != null);
    let value = (first.reduce((a, r) => a + r.byDate[dates[0]] / r.base, 0) / first.length) * 100;
    const points = [{ date: dates[0], value: r1(value) }];
    for (let k = 1; k < dates.length; k++) {
      const both = rows.filter((r) => r.byDate[dates[k]] != null && r.byDate[dates[k - 1]] != null);
      if (both.length) value *= both.reduce((a, r) => a + r.byDate[dates[k]] / r.byDate[dates[k - 1]], 0) / both.length;
      points.push({ date: dates[k], value: r1(value) });
    }
    const now = points.at(-1).value, prev = points.at(-2).value;
    return {
      code: g.code, name: g.name, emoji: g.emoji, categories: g.categories, item_count: members.length,
      value: now, change: r1(now - prev), change_pct: r1(((now - prev) / prev) * 100), points,
    };
  });
  return { base_date: dates.at(-1), base_days: BASE_DAYS, groups };
}
