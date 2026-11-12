// [샘플] 가격 예측 화면의 "계절 패턴 · 월별 반입량" 예시 데이터 (전국 도매시장, 품목 단위).
// 실제는 경매원장(price_unit_daily) 월별 집계: 월평균 경락가 = 그 달 총 금액 ÷ 총 물량, 반입량 = 그 달 총 물량(톤).
// 평년 = 최근 5년(올해 빼고) 같은 달 평균. 올해는 이번 달까지 실제, 남은 달은 예측.
import { ITEMS50 } from "./items50";
import { seeded, todayIso } from "../utils/format";

const r0 = (n) => Math.round(n);
export function mockSeasonal(item, { anchor, today = todayIso() } = {}) {
  const r = seeded(`seasonal|${item}`);
  const year = Number(today.slice(0, 4));
  const cur = Number(today.slice(5, 7)); // 이번 달 (1~12)
  const idx = Math.max(0, ITEMS50.findIndex((i) => i.code === item));
  const base = 800 + ((idx * 937) % 4200) + r() * 600; // 품목마다 다른 가격대 (원/kg)
  const peak = 1 + Math.floor(r() * 12); // 가장 비싼 달
  const amp = 0.15 + r() * 0.25;
  const curve = (m) => 1 + amp * Math.cos((2 * Math.PI * (m - peak)) / 12);
  const tons = 2000 + r() * 28000; // 한 달 반입량 규모 (톤)
  const harvest = ((peak + 5) % 12) + 1; // 물량은 대개 가격이 낮은 철에 많다
  const vcurve = (m) => Math.max(0.03, 1 + 0.9 * Math.cos((2 * Math.PI * (m - harvest)) / 12));
  const months = Array.from({ length: 12 }, (_, i) => i + 1);
  const normal = months.map((m) => r0(base * curve(m) * (0.95 + r() * 0.1)));
  const actual = months.map((m) => (m <= cur ? r0(base * curve(m) * (0.8 + r() * 0.45)) : null));
  // 예측: 이번 달 실제에서 이어서 계절 흐름대로 (이번 달 점에서 시작)
  const forecast = months.map((m) => (m < cur ? null : m === cur ? actual[m - 1] : r0((actual[cur - 1] * curve(m)) / curve(cur) * (0.97 + r() * 0.06))));
  // 예시 데이터를 예측 화면의 지금 시세(anchor)에 맞춰 크기만 조정 (그래프 사이 숫자가 어긋나 보이지 않게)
  if (anchor && actual[cur - 1]) {
    const f = anchor / actual[cur - 1];
    for (const arr of [normal, actual, forecast]) arr.forEach((v, i) => { if (v != null) arr[i] = r0(v * f); });
  }
  const vNormal = months.map((m) => r0(tons * vcurve(m) * (0.9 + r() * 0.2)));
  const vActual = months.map((m) => (m <= cur ? r0(tons * vcurve(m) * (0.75 + r() * 0.5) * (m === cur ? Number(today.slice(8, 10)) / 30 : 1)) : null));
  return {
    item, year, current_month: cur, normal_years: [year - 5, year - 1],
    price: { normal, actual, forecast },
    volume: { normal: vNormal, actual: vActual, partial_month: cur },
    source: `경매원장 ${year - 6}~${year} 월별`,
    sample: true,
  };
}
