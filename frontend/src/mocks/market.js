// 시세·수급·날씨 가짜 데이터 (Spring 담당 API 가 생기기 전까지 사용).
// 응답 모양은 docs/06_api_spec.md 2번 섹션의 "제안" 과 같다.
import { addDays, seeded, todayIso } from "../utils/format";
import { BASE_PRICE, ITEMS } from "./catalog";

/** 주말을 뺀 조사일 (KAMIS 는 토·일·공휴일 조사 없음. 공휴일은 단순화를 위해 생략) */
function businessDays(endIso, count) {
  const days = [];
  let d = endIso;
  while (days.length < count) {
    const wd = new Date(`${d}T00:00:00`).getDay();
    if (wd !== 0 && wd !== 6) days.unshift(d);
    d = addDays(d, -1);
  }
  return days;
}

const RETAIL_MARKUP = { 근채류: 1.9, 조미채소: 2.1, 과일류: 1.6, 과채류: 1.7, 엽채류: 2.4, 버섯류: 1.5 };

function series(code, days) {
  const rand = seeded(`hist|${code}`);
  const base = BASE_PRICE[code];
  const markup = RETAIL_MARKUP[ITEMS.find((i) => i.code === code)?.category] ?? 1.8;
  let p = base * (0.9 + rand() * 0.15);
  return days.map((date, i) => {
    p *= 1 + (rand() - 0.5) * 0.05;
    if (i === days.length - 1) p = base; // 마지막 날 = 오늘 기준가
    return { date, wholesale: Math.round(p), retail: Math.round(p * markup * (0.97 + rand() * 0.06)) };
  });
}

export function mockTodayPrices() {
  const days = businessDays(todayIso(), 30);
  const base_date = days.at(-1);
  const compared_date = days.at(-2);
  const items = ITEMS.map((info) => {
    const s = series(info.code, days);
    const now = s.at(-1);
    const prev = s.at(-2);
    const change = now.wholesale - prev.wholesale;
    return {
      item: info.code,
      name: info.name,
      emoji: info.emoji,
      category: info.category,
      price: now.wholesale,
      prev_price: prev.wholesale,
      change,
      change_pct: Math.round((change / prev.wholesale) * 1000) / 10,
      retail_price: now.retail,
      margin_pct: Math.round(((now.retail - now.wholesale) / now.wholesale) * 100),
    };
  });
  return { base_date, compared_date, market: "가락시장", unit: "kg", items };
}

export function mockPriceHistory(code, count = 30) {
  return { item: code, unit: "kg", points: series(code, businessDays(todayIso(), count)) };
}

export function mockMarketCompare(code) {
  const rand = seeded(`mkt|${code}`);
  const base = BASE_PRICE[code];
  const markets = ["가락시장", "강서시장", "대구북부", "광주각화", "산지공판장"];
  return { item: code, unit: "kg", markets: markets.map((m) => ({ market: m, price: Math.round(base * (0.85 + rand() * 0.3)) })) };
}

export function mockSupply(code) {
  const rand = seeded(`sup|${code}`);
  const normal = 800 + Math.round(rand() * 600);
  const now = new Date();
  const months = [];
  for (let i = -5; i <= 2; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1);
    months.push({
      month: `${d.getMonth() + 1}월`,
      production: Math.round(normal * (0.8 + rand() * 0.4)),
      normal,
      is_forecast: i > 0,
    });
  }
  const name = ITEMS.find((i) => i.code === code)?.name ?? code;
  return {
    item: code,
    unit: "톤",
    months,
    note: `[데모] ${now.getMonth() + 1}월 관측: ${name} 출하량은 평년 대비 소폭 감소 전망. 기상 악화 시 다음 달 가격 강세 예상.`,
  };
}
