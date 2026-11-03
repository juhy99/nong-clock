// 작물 추천 예비 데이터. ml-api 가 꺼져 있을 때 화면이 대신 쓴다.
// 작물 달력·계산 방식은 ml-api/app/core/crop_calendar.py, app/services/recommender.py 와 같다 (값을 바꾸면 둘 다 고칠 것).
import { addDays, daysBetween, todayIso } from "../utils/format";

export const LAND_TYPES = { open: "노지", house: "시설", paddy: "논", orchard: "과수원" };

// [작형, 심기 시작(월/일), 심기 끝, 첫 수확까지 일수, 수확 이어지는 일수, 10a당 수량(t), 10a당 생산비(만원)]
const CROPS = [
  ["tomato", "토마토", "🍅", "house", [3100, 3400, 3900, 4200, 4400, 4600, 3850, 3000, 2600, 2900, 3300, 3200], [
    ["촉성재배", "10/21", "11/30", 85, 100, 10, 2600], ["반촉성재배", "12/21", "2/10", 75, 90, 9, 2300],
    ["조숙재배", "5/1", "5/31", 45, 45, 5, 1500], ["노지억제재배", "5/11", "5/31", 70, 70, 6, 1400]]],
  ["cucumber", "오이", "🥒", "house", [2400, 2600, 2900, 3100, 2650, 2300, 1900, 1700, 2000, 2600, 2700, 2500], [
    ["촉성재배", "11/1", "12/20", 70, 100, 12, 2300], ["반촉성재배", "1/1", "2/20", 70, 100, 11, 2000],
    ["조숙재배", "3/1", "4/20", 70, 70, 9, 1500], ["억제재배", "9/1", "10/20", 40, 90, 8, 1600]]],
  ["lettuce", "상추", "🥬", "house", [5200, 5600, 4900, 4300, 3800, 3200, 2800, 3500, 5200, 6200, 5800, 5000], [
    ["겨울재배", "11/15", "12/10", 40, 80, 4, 1250], ["시설봄재배", "2/1", "3/20", 50, 60, 3.5, 1000], ["가을재배", "8/11", "8/31", 30, 50, 3, 900]]],
  ["paprika", "파프리카", "🫑", "house", [4600, 5000, 5300, 5600, 5300, 5050, 4500, 4300, 4200, 4400, 4500, 4600], [["겨울재배", "8/11", "9/10", 80, 240, 12, 4600]]],
  ["strawberry", "딸기", "🍓", "house", [15000, 14000, 12500, 11000, 9000, 7500, 6500, 8000, 9000, 10000, 12000, 14500], [["촉성재배", "9/11", "9/30", 70, 160, 4, 3500]]],
  ["green_onion", "대파", "🧅", "open", [2100, 2200, 2300, 2400, 2500, 2500, 2350, 2000, 1900, 2100, 2300, 2200], [
    ["월동 아주심기", "10/20", "11/25", 160, 50, 4.5, 520], ["봄뿌림재배", "5/1", "6/30", 152, 150, 5, 600]]],
  ["spinach", "시금치", "🥬", "open", [3800, 4000, 4400, 4600, 3900, 3000, 3200, 5000, 7500, 8000, 6000, 4500], [
    ["가을재배", "9/11", "11/30", 45, 110, 1.5, 280], ["봄재배", "2/1", "5/31", 40, 40, 1.3, 250], ["여름재배", "6/1", "8/31", 30, 30, 1.0, 260]]],
  ["onion", "양파", "🧅", "open", [1450, 1500, 1550, 1600, 1650, 1450, 1250, 1300, 1350, 1400, 1450, 1450], [["보통재배", "10/11", "11/20", 180, 50, 6.5, 560]]],
  ["bomdong", "봄동", "🥬", "open", [1900, 2000, 2100, 2100, 1700, 1600, 1800, 1900, 2000, 1900, 1900, 1900], [["월동재배", "9/1", "11/15", 75, 90, 2.5, 230]]],
  ["garlic", "마늘", "🧄", "open", [6900, 6950, 7000, 7050, 7100, 6800, 6200, 6000, 6300, 6500, 6700, 6800], [["보통재배", "9/21", "10/31", 240, 30, 1.3, 700]]],
  ["napa_cabbage", "배추", "🥬", "open", [1100, 1000, 1200, 1300, 1400, 1300, 900, 800, 1200, 1600, 1800, 1300], [
    ["가을재배", "8/21", "9/10", 55, 50, 10, 400], ["봄재배", "4/1", "5/20", 55, 25, 8, 380]]],
  ["potato", "감자", "🥔", "open", [1500, 1550, 1600, 1650, 1700, 1750, 1500, 1100, 1050, 1150, 1300, 1400], [["봄재배", "2/21", "3/31", 95, 30, 3, 450]]],
  ["carrot", "당근", "🥕", "open", [1650, 1700, 1800, 1900, 1950, 1850, 1700, 1500, 1400, 1500, 1600, 1600], [
    ["봄재배", "3/1", "4/30", 120, 50, 4, 430], ["가을재배", "7/1", "7/31", 125, 30, 4, 420]]],
  ["rice", "쌀", "🌾", "paddy", [2450, 2450, 2480, 2500, 2500, 2520, 2550, 2550, 2560, 2400, 2350, 2400], [["모내기", "5/11", "6/10", 130, 25, 0.53, 78]]],
  ["soybean", "콩", "🫘", "paddy", [5500, 5500, 5600, 5600, 5700, 5700, 5800, 5800, 5800, 5500, 5300, 5400], [["논콩", "6/1", "6/30", 125, 20, 0.25, 48]]],
  ["apple", "사과", "🍎", "orchard", null, null, "나무를 심고 3~5년 뒤부터 매년 9~11월 수확"],
  ["pear", "배", "🍐", "orchard", null, null, "나무를 심고 4~5년 뒤부터 매년 8~11월 수확"],
  ["peach", "복숭아", "🍑", "orchard", null, null, "나무를 심고 3~4년 뒤부터 매년 6~9월 수확"],
].map(([code, name, emoji, land_type, p, cl, note]) => ({
  code, name, emoji, land_type, p, note,
  cl: (cl ?? []).map(([n, from, to, dth, hd, yld, cost]) => ({ name: n, from: from.split("/").map(Number), to: to.split("/").map(Number), dth, hd, yld, cost })),
}));
const BY = Object.fromEntries(CROPS.map((c) => [c.code, c]));

const PYEONG_PER_10A = 302.5;
const VERSION = "demo+crop-calendar-sample";
const errorPct = (m) => (m <= 2 ? 17 : m <= 6 ? 20 : 23);
const cropOut = (c) => ({ code: c.code, name: c.name, emoji: c.emoji, land_type: c.land_type, land_type_name: LAND_TYPES[c.land_type], perennial: !!c.note });

function priceOn(c, iso, today) {
  const t = new Date(`${today}T00:00:00`);
  const m = daysBetween(`${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-15`, iso) / 30.44;
  const i = Math.floor(m), f = m - i;
  const g = (k) => c.p[((k % 12) + 12) % 12];
  return g(i) * (1 - f) + g(i + 1) * f;
}
function avgPrice(c, a, b, today) {
  const v = [];
  for (let d = a; d <= b; d = addDays(d, 7)) v.push(priceOn(c, d, today));
  return v.reduce((s, x) => s + x, 0) / v.length;
}
function inWin(iso, w) {
  const d = new Date(`${iso}T00:00:00`);
  const k = (d.getMonth() + 1) * 100 + d.getDate(), s = w.from[0] * 100 + w.from[1], e = w.to[0] * 100 + w.to[1];
  return s <= e ? k >= s && k <= e : k >= s || k <= e;
}
const croppingOn = (c, iso) => c.cl.find((w) => inWin(iso, w));

function evaluate(c, w, plant, area, today) {
  const h0 = addDays(plant, w.dth), h1 = addDays(h0, w.hd), a10 = area / PYEONG_PER_10A;
  const price = avgPrice(c, h0, h1, today), y = w.yld * a10, revenue = price * y * 1000, cost = w.cost * 1e4 * a10, margin = revenue - cost;
  return {
    crop: c.code, crop_name: c.name, emoji: c.emoji, land_type: c.land_type, area_pyeong: area, cropping: w.name,
    plant_date: plant, harvest_start: h0, harvest_end: h1, price_per_kg: Math.round(price), error_pct: errorPct(daysBetween(today, h0) / 30.44),
    yield_t: Math.round(y * 100) / 100, revenue: Math.round(revenue), cost: Math.round(cost), margin: Math.round(margin),
    margin_rate: Math.round((margin / revenue) * 1000) / 10, margin_per_pyeong: Math.round(margin / area),
    yield_t_per_10a: w.yld, cost_per_10a: w.cost * 1e4,
  };
}
const better = (a, b) => (!a || b.margin_rate > a.margin_rate + 0.5 ? b : a);

export const mockCropList = () => CROPS.map(cropOut);

export function mockRecommendCrops({ lands, start_date }) {
  const today = todayIso();
  const area = {};
  lands.forEach((l) => (area[l.type] = (area[l.type] ?? 0) + l.area_pyeong));
  const results = [], unavailable = [];
  CROPS.forEach((c) => {
    const a = area[c.land_type];
    if (!a) return;
    const base = { crop: c.code, crop_name: c.name, emoji: c.emoji, land_type: c.land_type };
    if (c.note) return unavailable.push({ ...base, reason: c.note, next_plant_date: null, next_cropping: null });
    const w = croppingOn(c, start_date);
    if (w) return results.push(evaluate(c, w, start_date, a, today));
    let next = null;
    for (let k = 1; k < 370 && !next; k++) {
      const d = addDays(start_date, k), nw = croppingOn(c, d);
      if (nw) next = [d, nw.name];
    }
    unavailable.push({ ...base, reason: "심는 시기가 아니에요", next_plant_date: next?.[0] ?? null, next_cropping: next?.[1] ?? null });
  });
  results.sort((x, y) => y.margin - x.margin);
  return { start_date, results, unavailable, model_version: VERSION };
}

export function mockPlantingDates({ crop, area_pyeong }) {
  const c = BY[crop];
  if (!c) throw Object.assign(new Error(`unknown crop: ${crop}`), { status: 404 });
  if (c.note) return { crop: cropOut(c), note: c.note, best: null, top: [], points: [], model_version: VERSION };
  const today = todayIso();
  const points = Array.from({ length: 53 }, (_, k) => {
    const d = addDays(today, k * 7), w = croppingOn(c, d);
    return { plant_date: d, option: w ? evaluate(c, w, d, area_pyeong, today) : null };
  });
  let best = null;
  const per = {};
  points.forEach(({ option: o }) => {
    if (!o) return;
    best = better(best, o);
    per[o.cropping] = better(per[o.cropping], o);
  });
  const top = Object.values(per).sort((a, b) => b.margin_rate - a.margin_rate).slice(0, 3);
  return { crop: cropOut(c), note: null, best, top, points, model_version: VERSION };
}

export function mockPricePath(code) {
  const c = BY[code];
  if (!c) throw Object.assign(new Error(`unknown crop: ${code}`), { status: 404 });
  if (c.note) return { crop: cropOut(c), points: [], model_version: VERSION };
  const today = todayIso();
  const points = Array.from({ length: 57 }, (_, k) => {
    const d = addDays(today, k * 7), v = priceOn(c, d, today), e = (errorPct(daysBetween(today, d) / 30.44) / 100) * 0.7;
    return { date: d, price: Math.round(v), lower: Math.round(v * (1 - e)), upper: Math.round(v * (1 + e)) };
  });
  return { crop: cropOut(c), points, model_version: VERSION };
}
