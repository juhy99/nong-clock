// 작물 추천 예비 데이터. ml-api 가 꺼져 있을 때 화면이 대신 쓴다.
// 작물 달력·계산 방식은 ml-api/app/core/crop_calendar.py, app/core/markets.py, app/services/recommender.py 와 같다 (값을 바꾸면 둘 다 고칠 것).
import { addDays, daysBetween, todayIso } from "../utils/format";
import { MARKETS, marketFactor } from "./market";

// 시·도 대략 중심 (가까운 도매시장 고르기용)
export const SIDO_CENTER = {
  서울: [37.56, 126.98], 부산: [35.18, 129.08], 대구: [35.87, 128.6], 인천: [37.46, 126.7], 광주: [35.16, 126.85], 대전: [36.35, 127.38],
  울산: [35.54, 129.31], 세종: [36.48, 127.29], 경기: [37.41, 127.25], 강원: [37.8, 128.2], 충북: [36.8, 127.7], 충남: [36.5, 126.8],
  전북: [35.72, 127.15], 전남: [34.86, 126.99], 경북: [36.4, 128.9], 경남: [35.24, 128.25], 제주: [33.49, 126.53],
};
const km = ([a, b], [c, d]) => {
  const r = Math.PI / 180, x = (d - b) * r * Math.cos(((a + c) / 2) * r), y = (c - a) * r;
  return Math.round(Math.sqrt(x * x + y * y) * 6371);
};
/** 시·도에서 가까운 공영 도매시장 순서 (거리 km 포함) */
export function marketsNear(sido) {
  const c = SIDO_CENTER[sido] ?? SIDO_CENTER.서울;
  return MARKETS.filter((m) => m.lat != null).map((m) => ({ code: m.code, name: m.name, sido: m.sido, km: km(c, [m.lat, m.lon]) })).sort((a, b) => a.km - b.km);
}
// 시장별 가격 = 전국 도매시장 평균 예측 × 시장 계수 (시세 화면 가짜 데이터와 같은 계수 · 추정)
const mktFactor = (crop, market) => (!market || market === "national" ? 1 : marketFactor(crop, market));
/** 같은 계획을 다른 시장에 팔았을 때 (매출만 시장 계수만큼 바뀌고 경영비는 같다) */
function atMarket(o, market) {
  const f = mktFactor(o.crop, market), revenue = Math.round(o.revenue * f), margin = revenue - o.cost;
  return { revenue, margin, margin_rate: Math.round((margin / revenue) * 1000) / 10, price_per_kg: Math.round(o.price_per_kg * f), factor: f };
}
function applyMarket(o, region, market) {
  const near = marketsNear(region);
  const pick = market ?? near[0].code;
  const info = MARKETS.find((m) => m.code === pick);
  const at = atMarket(o, pick), e = o.error_pct / 100, f = at.factor;
  const compare = [...near.slice(0, 4), ...(near.slice(0, 4).some((m) => m.code === "110001") ? [] : [near.find((m) => m.code === "110001")])]
    .map((m) => ({ ...m, ...atMarket(o, m.code) }))
    .concat([{ code: "national", name: "전국 평균", km: null, ...atMarket(o, "national") }]);
  return {
    ...o, ...at,
    national_price_per_kg: o.price_per_kg, national_margin: o.margin,
    market: { code: pick, name: info?.name ?? pick, km: near.find((m) => m.code === pick)?.km ?? null }, region,
    margin_per_pyeong: Math.round(at.margin / o.area_pyeong),
    margin_low: Math.round(at.revenue * (1 - e) - o.cost), margin_high: Math.round(at.revenue * (1 + e) - o.cost),
    shipments: o.shipments.map((m) => ({ ...m, price_per_kg: Math.round(m.price_per_kg * f), revenue: Math.round(m.revenue * f) })),
    per_10a: { ...o.per_10a, revenue: Math.round(o.per_10a.revenue * f), income: Math.round(o.per_10a.revenue * f - o.per_10a.cost) },
    market_compare: compare,
  };
}

export const LAND_TYPES = { open: "노지", house: "시설", paddy: "논", orchard: "과수원" };

// [작형, 심기 시작(월/일), 심기 끝, 심고 첫 수확까지 일수, 수확 이어지는 일수, 10a당 수량(t), 10a당 경영비(만원), 수확 뒤 보관 일수]
// 수량·경영비·가격 수준: 농촌진흥청 2024년도 농산물소득조사(10a당). 양파·봄동·마늘·쌀·콩은 조사표에 없어 예시 값.
// 심는 시기·수확 기간: 농사로 재배력 작형 기준. 보관: 알맞은 저온 저장 기준 팔 수 있는 기간.
// 농촌진흥청 2024년도 농산물소득조사 (10a당, 천원·kg·원/kg) — 우리 작물과 맞는 조사표 행
const RDA = {
  tomato: { row: "토마토(토경)", revenue: 20510, cost: 9768, income: 10741, kg: 6226, price: 3294 },
  cucumber: { row: "시설오이", revenue: 25184, cost: 12300, income: 12884, kg: 10505, price: 2397 },
  lettuce: { row: "시설상추", revenue: 11629, cost: 6609, income: 5020, kg: 3315, price: 3508 },
  paprika: { row: "시설파프리카", revenue: 40882, cost: 29421, income: 11461, kg: 11233, price: 3640 },
  strawberry: { row: "딸기(토경)", revenue: 26307, cost: 15621, income: 10686, kg: 2893, price: 9094 },
  green_onion: { row: "대파", revenue: 4570, cost: 1915, income: 2655, kg: 3821, price: 1196 },
  spinach: { row: "노지시금치", revenue: 3787, cost: 1205, income: 2581, kg: 978, price: 3870 },
  napa_cabbage: { row: "가을배추", revenue: 4137, cost: 1534, income: 2603, kg: 6155, price: 672 },
  potato: { row: "봄감자", revenue: 2693, cost: 1444, income: 1250, kg: 2263, price: 1190 },
  carrot: { row: "당근", revenue: 6275, cost: 2462, income: 3813, kg: 3542, price: 1772 },
};
const RDA_ALL = { napa_cabbage: true, potato: true }; // 작형마다 조사표 행이 따로 있음 (봄·가을배추, 봄·가을감자)
// 상품화율(팔 수 있는 상품 비율) — 추정값. 공식 통계 아님
const MARKETABLE = { tomato: 0.92, cucumber: 0.9, lettuce: 0.9, paprika: 0.9, strawberry: 0.85, green_onion: 0.95, spinach: 0.9, onion: 0.93, bomdong: 0.9, garlic: 0.9, napa_cabbage: 0.88, potato: 0.9, carrot: 0.88, rice: 1, soybean: 0.95 };

const CROPS = [
  ["tomato", "토마토", "🍅", "house", [3300, 3200, 3000, 2700, 2200, 1800, 2200, 3300, 4200, 4500, 3900, 3500], [
    ["촉성재배", "9/21", "11/20", 80, 150, 6.2, 977, 10], ["반촉성재배", "1/11", "2/20", 75, 90, 4.5, 800, 10], ["억제재배", "7/11", "8/10", 60, 80, 3.5, 650, 10]]],
  ["cucumber", "오이", "🥒", "house", [3000, 2800, 2500, 2000, 1600, 1500, 1900, 2600, 2800, 2300, 2200, 2800], [
    ["촉성재배", "10/11", "12/10", 40, 110, 10.5, 1230, 7], ["반촉성재배", "1/11", "2/28", 35, 90, 8, 950, 7], ["억제재배", "8/21", "9/20", 30, 70, 6, 750, 7]]],
  ["lettuce", "상추", "🥬", "house", [3600, 3200, 2800, 2500, 2400, 3000, 4200, 5200, 4800, 3800, 3300, 3500], [
    ["겨울재배", "10/21", "12/10", 40, 60, 3.0, 600, 10], ["봄재배", "2/1", "3/31", 35, 45, 2.6, 500, 10], ["가을재배", "8/21", "9/20", 30, 45, 2.4, 480, 10]]],
  ["paprika", "파프리카", "🫑", "house", [4000, 3800, 3500, 3200, 3000, 3200, 3600, 4200, 4500, 4000, 3800, 4000], [["장기재배", "8/1", "8/31", 90, 240, 11.2, 2942, 21]]],
  ["strawberry", "딸기", "🍓", "house", [10500, 9500, 8000, 6500, 5500, 6000, 7000, 8000, 9000, 11000, 13000, 12500], [["촉성재배", "9/1", "9/25", 75, 165, 2.9, 1562, 5]]],
  ["green_onion", "대파", "🧅", "open", [1300, 1400, 1500, 1400, 1200, 1100, 1100, 1200, 1300, 1100, 1000, 1200], [
    ["월동재배", "7/11", "8/31", 140, 110, 3.8, 192, 14], ["봄재배", "3/21", "5/31", 120, 60, 3.5, 180, 14]]],
  ["spinach", "시금치", "🥬", "open", [3200, 3000, 3300, 3500, 3800, 4500, 6000, 7000, 6000, 4500, 3500, 3300], [
    ["가을재배", "8/21", "9/30", 40, 20, 1.0, 121, 10], ["월동재배", "10/1", "11/15", 90, 60, 1.0, 121, 10], ["봄재배", "3/1", "4/15", 40, 15, 0.9, 115, 10]]],
  ["onion", "양파", "🧅", "open", [1100, 1150, 1200, 1250, 1000, 900, 950, 1000, 1050, 1100, 1150, 1100], [["보통재배", "10/21", "11/20", 200, 20, 6.6, 280, 210]]],
  ["bomdong", "봄동", "🥬", "open", [1600, 1500, 1400, 1300, 1300, 1300, 1300, 1300, 1400, 1500, 1600, 1700], [["월동재배", "9/1", "10/20", 90, 80, 2.0, 90, 10]]],
  ["garlic", "마늘", "🧄", "open", [6900, 6950, 7000, 7050, 7100, 6800, 6200, 6000, 6300, 6500, 6700, 6800], [["난지형", "9/21", "10/31", 235, 20, 1.4, 300, 240]]],
  ["napa_cabbage", "배추", "🥬", "open", [800, 750, 800, 900, 700, 600, 900, 1100, 1000, 800, 600, 700], [
    ["가을재배", "8/21", "9/10", 70, 20, 6.2, 153, 60], ["봄재배", "3/21", "4/30", 60, 15, 7.1, 134, 20]]],
  ["potato", "감자", "🥔", "open", [1300, 1350, 1400, 1450, 1300, 1100, 1000, 1000, 1050, 1100, 1200, 1250], [
    ["봄재배", "3/1", "3/31", 100, 20, 2.3, 144, 120], ["가을재배", "8/11", "8/31", 100, 15, 1.8, 168, 120]]],
  ["carrot", "당근", "🥕", "open", [1650, 1700, 1800, 1900, 1950, 1850, 1700, 1500, 1400, 1500, 1600, 1600], [
    ["봄재배", "3/11", "4/20", 110, 20, 3.5, 246, 120], ["가을재배", "7/11", "8/10", 110, 30, 3.5, 246, 120]]],
  ["rice", "쌀", "🌾", "paddy", [2450, 2450, 2480, 2500, 2500, 2520, 2550, 2550, 2560, 2400, 2350, 2400], [["모내기", "5/11", "6/10", 130, 20, 0.52, 72, 365]]],
  ["soybean", "콩", "🫘", "paddy", [5500, 5500, 5600, 5600, 5700, 5700, 5800, 5800, 5800, 5500, 5300, 5400], [["논콩", "6/1", "6/30", 125, 15, 0.23, 50, 365]]],
  ["apple", "사과", "🍎", "orchard", null, null, "나무를 심고 3~5년 뒤부터 매년 9~11월 수확"],
  ["pear", "배", "🍐", "orchard", null, null, "나무를 심고 4~5년 뒤부터 매년 8~11월 수확"],
  ["peach", "복숭아", "🍑", "orchard", null, null, "나무를 심고 3~4년 뒤부터 매년 6~9월 수확"],
].map(([code, name, emoji, land_type, p, cl, note]) => ({
  // 조사표 가격은 상품·비품을 섞은 평균 수취가라 상품화율을 또 빼지 않는다(1). 조사표 없는 작물만 추정 상품화율 적용
  code, name, emoji, land_type, p, note, rda: RDA[code] ?? null, mk: RDA[code] ? 1 : MARKETABLE[code] ?? 0.9,
  // 작형 수량·경영비 출처: 농진청 조사표 행과 맞는 작형은 "rda", 나머지는 그 행을 작형에 맞게 줄이거나 늘린 추정값 "est"
  cl: (cl ?? []).map(([n, from, to, dth, hd, yld, cost, store], i) => ({
    name: n, from: from.split("/").map(Number), to: to.split("/").map(Number), dth, hd, yld, cost, store,
    src: RDA_ALL[code] || (RDA[code] && i === 0) ? "rda" : "est",
  })),
}));
/** 수확 기간 안 주별 출하 비중: 여러 번 따는 작물은 처음·끝에 적고 가운데 많게, 한 번에 거두는 작물은 고르게 */
const shipWeight = (t, multi) => (!multi ? 1 : t < 0.3 ? 0.4 + 2 * t : t < 0.75 ? 1 : 1 - 1.6 * (t - 0.75));

// 가격 수준 맞추기: 농진청 조사표가 있는 작물은 대표 작형(첫 작형)을 심는 기간 가운데 날 심었을 때의
// 출하량 가중 평균가가 조사표 농가수취가격과 같아지도록 월별 가격(계절 모양은 추정)을 통째로 늘리거나 줄인다
function calibrate(c) {
  if (!c.rda || !c.p) return;
  const w = c.cl[0], y = 2026, mid = Math.round(((w.to[0] - w.from[0] + 12) % 12) * 15 + (w.to[1] - w.from[1]) / 2);
  const plant = addDays(`${y}-${String(w.from[0]).padStart(2, "0")}-${String(w.from[1]).padStart(2, "0")}`, mid);
  const h0 = addDays(plant, w.dth), h1 = addDays(h0, w.hd), multi = w.hd > 30;
  const pts = [];
  for (let d = h0; d <= h1; d = addDays(d, 7)) pts.push(d);
  let sw = 0, sp = 0;
  pts.forEach((d, i) => {
    const wt = shipWeight(pts.length > 1 ? i / (pts.length - 1) : 0, multi), m = new Date(`${d}T00:00:00`).getMonth();
    sw += wt; sp += wt * c.p[m];
  });
  const k = c.rda.price / (sp / sw);
  c.p = c.p.map((v) => Math.round((v * k) / 10) * 10);
}
CROPS.forEach(calibrate);

const BY = Object.fromEntries(CROPS.map((c) => [c.code, c]));

const PYEONG_PER_10A = 302.5;
const VERSION = "demo+crop-calendar-sample";
const errorPct = (m) => (m <= 2 ? 17 : m <= 6 ? 20 : 23);
const cropOut = (c) => ({ code: c.code, name: c.name, emoji: c.emoji, land_type: c.land_type, land_type_name: LAND_TYPES[c.land_type], perennial: !!c.note });

function priceOn(c, iso, today) {
  const t = new Date(`${today}T00:00:00`);
  const m = daysBetween(`${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-15`, iso) / 30.44;
  const i = Math.floor(m), f = m - i;
  const g = (k) => c.p[(((t.getMonth() + k) % 12) + 12) % 12]; // c.p 는 1~12월 순서
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


// rent: { land, machine } 만원 — 사용자가 넣은 이번 작기 임대료. 경영비에 그대로 더한다
function evaluate(c, w, plant, area, today, rent = {}) {
  const h0 = addDays(plant, w.dth), h1 = addDays(h0, w.hd), a10 = area / PYEONG_PER_10A, multi = w.hd > 30;
  const weeks = [];
  for (let d = h0; d <= h1; d = addDays(d, 7)) weeks.push(d);
  const ws = weeks.map((d, i) => shipWeight(weeks.length > 1 ? i / (weeks.length - 1) : 0, multi));
  const wsum = ws.reduce((x, y) => x + y, 0);
  const total_t = w.yld * a10, sell_t = total_t * c.mk;
  const ship = {};
  let revenue = 0;
  weeks.forEach((d, i) => {
    const t = (sell_t * ws[i]) / wsum, pr = priceOn(c, d, today), k = d.slice(0, 7);
    revenue += t * 1000 * pr;
    ship[k] = ship[k] ?? { month: k, t: 0, won: 0 };
    ship[k].t += t; ship[k].won += t * 1000 * pr;
  });
  const base_cost = w.cost * 1e4 * a10, land_rent = (rent.land ?? 0) * 1e4, machine_rent = (rent.machine ?? 0) * 1e4;
  const cost = base_cost + land_rent + machine_rent, margin = revenue - cost;
  const ep = errorPct(daysBetween(today, h0) / 30.44), e = ep / 100;
  const R = Math.round;
  return {
    crop: c.code, crop_name: c.name, emoji: c.emoji, land_type: c.land_type, area_pyeong: area, cropping: w.name,
    plant_date: plant, harvest_start: h0, harvest_end: h1, harvest_days: w.hd, days_to_harvest: w.dth, multi_harvest: multi,
    storage_days: w.store, storage_end: addDays(h1, w.store),
    price_per_kg: R(revenue / (sell_t * 1000)), error_pct: ep,
    yield_t: R(total_t * 100) / 100, sellable_t: R(sell_t * 100) / 100, marketable_rate: c.mk,
    revenue: R(revenue), base_cost: R(base_cost), land_rent: R(land_rent), machine_rent: R(machine_rent), cost: R(cost), margin: R(margin),
    margin_rate: R((margin / revenue) * 1000) / 10, margin_per_pyeong: R(margin / area),
    margin_low: R(revenue * (1 - e) - cost), margin_high: R(revenue * (1 + e) - cost),
    yield_t_per_10a: w.yld, cost_per_10a: w.cost * 1e4, source: w.src,
    rda: c.rda && { ...c.rda, revenue: c.rda.revenue * 1000, cost: c.rda.cost * 1000, income: c.rda.income * 1000 },
    per_10a: { revenue: R(revenue / a10), cost: R(base_cost / a10), income: R((revenue - base_cost) / a10) },
    shipments: Object.values(ship).map((m) => ({ month: m.month, t: R(m.t * 100) / 100, price_per_kg: R(m.won / (m.t * 1000)), revenue: R(m.won) })),
  };
}
const better = (a, b) => (!a || b.margin_rate > a.margin_rate + 0.5 ? b : a);

export const mockCropList = () => CROPS.map(cropOut);

export function mockRecommendCrops({ lands, start_date, region = "서울", market = null }) {
  const today = todayIso();
  const area = {}, rent = {};
  lands.forEach((l) => {
    area[l.type] = (area[l.type] ?? 0) + l.area_pyeong;
    const r = (rent[l.type] = rent[l.type] ?? { land: 0, machine: 0 });
    r.land += l.land_rent ?? 0; r.machine += l.machine_rent ?? 0;
  });
  const results = [], unavailable = [];
  CROPS.forEach((c) => {
    const a = area[c.land_type];
    if (!a) return;
    const base = { crop: c.code, crop_name: c.name, emoji: c.emoji, land_type: c.land_type };
    if (c.note) return unavailable.push({ ...base, reason: c.note, next_plant_date: null, next_cropping: null });
    const w = croppingOn(c, start_date);
    if (w) return results.push(applyMarket(evaluate(c, w, start_date, a, today, rent[c.land_type]), region, market));
    let next = null;
    for (let k = 1; k < 370 && !next; k++) {
      const d = addDays(start_date, k), nw = croppingOn(c, d);
      if (nw) next = [d, nw.name];
    }
    unavailable.push({ ...base, reason: "심는 시기가 아니에요", next_plant_date: next?.[0] ?? null, next_cropping: next?.[1] ?? null });
  });
  results.sort((x, y) => y.margin - x.margin);
  const near = marketsNear(region);
  return { start_date, region, market: results[0]?.market ?? { code: market ?? near[0].code, name: MARKETS.find((m) => m.code === (market ?? near[0].code))?.name }, results, unavailable, model_version: VERSION };
}

export function mockPlantingDates({ crop, area_pyeong, land_rent = 0, machine_rent = 0, region = "서울", market = null }) {
  const c = BY[crop];
  if (!c) throw Object.assign(new Error(`unknown crop: ${crop}`), { status: 404 });
  if (c.note) return { crop: cropOut(c), note: c.note, best: null, top: [], points: [], model_version: VERSION };
  const today = todayIso();
  const points = Array.from({ length: 53 }, (_, k) => {
    const d = addDays(today, k * 7), w = croppingOn(c, d);
    return { plant_date: d, option: w ? applyMarket(evaluate(c, w, d, area_pyeong, today, { land: land_rent, machine: machine_rent }), region, market) : null };
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
