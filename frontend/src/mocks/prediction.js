// ML API 가 꺼져 있을 때 쓰는 가짜 예측. 응답 모양은 POST /predict 와 똑같다.
import { addDays, seeded, todayIso } from "../utils/format";
import { BASE_PRICE, ITEMS } from "./catalog";

export function mockPredict({ item, horizon, region = "national" }) {
  const info = ITEMS.find((i) => i.code === item) ?? ITEMS[0];
  const base = BASE_PRICE[info.code] ?? 1000;
  const rand = seeded(`${info.code}|${region}|${todayIso()}`);
  const today = todayIso();

  const history = [];
  let p = base * (0.88 + rand() * 0.08);
  for (let i = 14; i > 0; i--) {
    p *= 1 + (rand() - 0.5) * 0.03;
    history.push({ date: addDays(today, -i), price: Math.round(p) });
  }
  history.push({ date: today, price: base });

  const drift = (rand() - 0.45) * 0.02;
  const forecast = [];
  p = base;
  for (let t = 1; t <= horizon; t++) {
    p *= 1 + drift + (rand() - 0.5) * 0.008;
    const band = p * 0.03 * Math.sqrt(t);
    forecast.push({ date: addDays(today, t), price: Math.round(p), lower: Math.round(p - band), upper: Math.round(p + band) });
  }
  const predicted = forecast.at(-1).price;

  return {
    item: info.code,
    item_name: info.name,
    unit: "kg",
    region,
    horizon,
    base_date: today,
    base_price: base,
    history,
    forecast,
    predicted_price: predicted,
    change_pct: Math.round(((predicted - base) / base) * 1000) / 10,
    confidence: Math.max(0, 92 - Math.floor(horizon / 2) - Math.floor(rand() * 6)),
    alerts:
      horizon >= 14
        ? [{ start: addDays(today, 7), end: addDays(today, 9), reason: "[데모] 기온 편차 +2.4σ, 강수량 평년 대비 180% 예상", mape_normal: 6.2, mape_anomaly: 19.8 }]
        : [],
    model_version: "mock",
  };
}

export function mockTopMovers(horizon, limit) {
  return ITEMS.map((i) => mockPredict({ item: i.code, horizon }))
    .map((p) => ({ item: p.item, item_name: p.item_name, unit: "kg", predicted_price: p.predicted_price, change_pct: p.change_pct, confidence: p.confidence }))
    .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct))
    .slice(0, limit);
}
