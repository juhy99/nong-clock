// ML API 가 꺼져 있을 때 쓰는 가짜 예측. 응답 모양은 POST /predict 와 똑같다.
// 그래프 선(가격)은 가짜지만, 오차 범위(띠)·신뢰도·참고용 표시는 실제 모델 검증 오차(shared/model_accuracy.json)를 따른다.
// 최대 365일: 품목마다 고정된 계절 모양(1년 주기) + 작은 흔들림. 시장별 값 = 전국 예측 × 시장 계수 (ml-api markets.py 와 같은 규칙)
import { addDays, seeded, todayIso } from "../utils/format";
import { BASE_PRICE, ITEMS } from "./catalog";
import { IN50 } from "./items50";
import { MARKETS, marketFactor } from "./market";
import { MODEL_MAX_DAYS, confidenceOf, errorPct, referenceOf } from "./accuracy";

export const MAX_HORIZON = 365;
export const LONG_RANGE_DAYS = MODEL_MAX_DAYS; // 6개월보다 먼 예측은 모델이 없어 범위를 더 넓히고 "참고용" 안내

const dayOfYear = (iso) => {
  const d = new Date(`${iso}T00:00:00`);
  return Math.floor((d - new Date(d.getFullYear(), 0, 1)) / 86400000);
};

/** 품목 계절 모양: 1 ± 진폭 (진폭 8~30%, 가장 비싼 때는 품목마다 다름) */
function season(item, iso) {
  const r = seeded(`season|${item}`);
  const amp = 0.08 + r() * 0.22, peak = Math.floor(r() * 365);
  return 1 + amp * Math.cos((2 * Math.PI * (dayOfYear(iso) - peak)) / 365);
}

/** 오차 범위 비율 = 모델 검증 오차(WAPE) — 품목·예측 기간별 (accuracy.js) */
export const bandRatio = (item, t) => errorPct(item, t) / 100;

export function mockPredict({ item, horizon, market = "national" }) {
  const info = ITEMS.find((i) => i.code === item) ?? ITEMS[0];
  const h = Math.min(Math.max(1, horizon), MAX_HORIZON);
  const f = market === "national" ? 1 : marketFactor(info.code, market);
  const base = Math.round((BASE_PRICE[info.code] ?? 1000) * f);
  const rand = seeded(`${info.code}|${market}|${todayIso()}`);
  const today = todayIso();
  const s0 = season(info.code, today);

  const history = [];
  let p = base * (0.9 + rand() * 0.08);
  for (let i = 14; i > 0; i--) {
    p *= 1 + (rand() - 0.5) * 0.03;
    history.push({ date: addDays(today, -i), price: Math.round(p) });
  }
  history.push({ date: today, price: base });

  const forecast = [];
  let wob = 0;
  for (let t = 1; t <= h; t++) {
    const d = addDays(today, t);
    wob = wob * 0.9 + (rand() - 0.5) * 0.02; // 천천히 흔들리는 잡음
    const v = base * (season(info.code, d) / s0) * (1 + wob);
    const band = v * bandRatio(info.code, t);
    forecast.push({ date: d, price: Math.round(v), lower: Math.round(v - band), upper: Math.round(v + band) });
  }
  const predicted = forecast.at(-1).price;
  const m = MARKETS.find((x) => x.code === market);

  return {
    item: info.code,
    item_name: info.name,
    code4: info.code4,
    unit: "kg",
    market,
    market_name: m?.name ?? "전국 평균",
    horizon: h,
    base_date: today,
    base_price: base,
    history,
    forecast,
    predicted_price: predicted,
    change_pct: Math.round(((predicted - base) / base) * 1000) / 10,
    error_pct: Math.round(errorPct(info.code, h) * 10) / 10, // 고른 날의 예측 오차 (±%, 검증 WAPE)
    reference: referenceOf(info.code, h), // "far" 6개월보다 멂 · "baseline" 기준선보다 나쁜 품목·기간 · null
    confidence: confidenceOf(info.code, h),
    alerts:
      h >= 14
        ? [{ start: addDays(today, 7), end: addDays(today, 9), reason: "[데모] 기온 편차 +2.4σ, 강수량 평년 대비 180% 예상", mape_normal: 6.2, mape_anomaly: 19.8 }]
        : [],
    model_version: "mock",
  };
}

export function mockTopMovers(horizon, limit) {
  return ITEMS.filter((i) => IN50.has(i.code)).map((i) => mockPredict({ item: i.code, horizon, market: "national" }))
    .map((p) => ({ item: p.item, item_name: p.item_name, unit: "kg", predicted_price: p.predicted_price, change_pct: p.change_pct, confidence: p.confidence, error_pct: p.error_pct, reference: p.reference }))
    .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
    .slice(0, limit);
}
