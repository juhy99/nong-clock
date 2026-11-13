// 작물 추천 예비 데이터. ml-api 가 꺼져 있을 때 화면이 대신 쓴다.
// 11-13: 화면은 ml-api 실제 계산만 씀(가짜 계산으로 넘어가지 않음). 여기서는 LAND_TYPES · SIDO_LIST 만 쓰이고, 아래 계산은 예전 예비 데이터(쓰지 않음).
import { addDays, daysBetween, todayIso } from "../utils/format";
import { marketFactor } from "./market";
import MARKET_DATA from "../../../shared/markets.json";
import { phCheck, soilPhFromPrev } from "./soil_ph";
import { errorPct, referenceOf } from "./accuracy";

// 토지 위치(시·도) → 그 시·도 안 공영 도매시장끼리 비교 (11/4 팀 결정: 수확한 지역 안의 도매시장에서 판다고 가정, 운송비·유통 마진은 계산하지 않음)
// 시·도에 공영 도매시장이 없으면(세종·제주) 다른 지역 시장을 섞지 않고 전국 도매시장 평균으로 계산
export const SIDO_LIST = MARKET_DATA.sido;
const NATIONAL = { code: "national", name: "전국 평균", sido: null };
/** { markets: [{code,name,sido}], none: 시·도 안에 시장이 없어 전국 평균을 쓴 경우 true } */
export function marketsInSido(sido) {
  const here = MARKET_DATA.markets.filter((m) => m.sido === sido).map(({ code, name, sido: s }) => ({ code, name, sido: s }));
  return here.length ? { markets: here, none: false } : { markets: [NATIONAL], none: true };
}
// 시장별 가격 = 전국 도매시장 평균 예측 × 시장 계수 (시세 화면 가짜 데이터와 같은 계수 · 추정)
const mktFactor = (crop, market) => (!market || market === "national" ? 1 : marketFactor(crop, market));
/** 같은 계획을 다른 시장에 팔았을 때 (매출만 시장 계수만큼 바뀌고 경영비는 같다) */
function atMarket(o, market) {
  const f = mktFactor(o.crop, market), revenue = Math.round(o.revenue * f), margin = revenue - o.cost;
  return { revenue, margin, margin_rate: Math.round((margin / revenue) * 1000) / 10, price_per_kg: Math.round(o.price_per_kg * f), factor: f };
}
/** 시·도 안 시장마다 계산 → 순이익이 가장 높은 시장을 대표 결과로 (market 을 주면 그 시장) */
function applyRegion(o, region, market) {
  const { markets, none } = marketsInSido(region);
  const compare = markets.map((m) => ({ ...m, ...atMarket(o, m.code) }));
  const best = compare.reduce((a, b) => (b.margin > a.margin ? b : a));
  const pick = compare.find((m) => m.code === market) ?? best;
  const at = atMarket(o, pick.code), e = o.error_pct / 100, f = at.factor;
  return {
    ...o, ...at,
    national_price_per_kg: o.price_per_kg, national_margin: o.margin,
    market: { code: pick.code, name: pick.name }, region, no_market: none,
    margin_per_pyeong: Math.round(at.margin / o.area_pyeong),
    margin_low: Math.round(at.revenue * (1 - e) - o.cost), margin_high: Math.round(at.revenue * (1 + e) - o.cost),
    shipments: o.shipments.map((m) => ({ ...m, price_per_kg: Math.round(m.price_per_kg * f), revenue: Math.round(m.revenue * f) })),
    per_10a: { ...o.per_10a, revenue: Math.round(o.per_10a.revenue * f), income: Math.round(o.per_10a.revenue * f - o.per_10a.cost) },
    market_compare: compare.map((m) => ({ ...m, best: m.code === best.code })),
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
// 예측 오차(±%) = 모델 검증 오차(WAPE), 작물·수확까지 남은 날 기준 (accuracy.js, ml-api accuracy.py 와 같음)
const errorPctFor = (crop, days) => Math.round(errorPct(crop, Math.max(1, days)));
const cropOut = (c) => ({ code: c.code, name: c.name, emoji: c.emoji, land_type: c.land_type, land_type_name: LAND_TYPES[c.land_type], perennial: !!c.note });

function priceOn(c, iso, today) {
  const t = new Date(`${today}T00:00:00`);
  const m = daysBetween(`${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-15`, iso) / 30.44;
  const i = Math.floor(m), f = m - i;
  const g = (k) => c.p[(((t.getMonth() + k) % 12) + 12) % 12]; // c.p 는 1~12월 순서
  return g(i) * (1 - f) + g(i + 1) * f;
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
  const ep = errorPctFor(c.code, daysBetween(today, h0)), e = ep / 100;
  const R = Math.round;
  return {
    crop: c.code, crop_name: c.name, emoji: c.emoji, land_type: c.land_type, area_pyeong: area, cropping: w.name,
    plant_date: plant, harvest_start: h0, harvest_end: h1, harvest_days: w.hd, days_to_harvest: w.dth, multi_harvest: multi,
    storage_days: w.store, storage_end: addDays(h1, w.store),
    price_per_kg: R(revenue / (sell_t * 1000)), error_pct: ep, reference: referenceOf(c.code, daysBetween(today, h0)),
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

export const TOP_N = 3; // 작물 정보 탭 "추천 상위" 기준
const tenDay = ([m, d]) => `${m}월 ${d <= 10 ? "상순" : d <= 20 ? "중순" : "하순"}`;
/** 추천 상위(TOP_N)에 없는 작물마다 이유 (ml-api recommender.excluded 와 같은 문장) */
function excludedReasons(results, lands, start) {
  const owned = lands.filter((l) => l.area_pyeong > 0).map((l) => l.type);
  const ownedTxt = Object.keys(LAND_TYPES).filter((k) => owned.includes(k)).map((k) => LAND_TYPES[k]).join("·") || "없음";
  const month = new Date(`${start}T00:00:00`).getMonth() + 1;
  const rank = Object.fromEntries(results.map((r, i) => [r.crop, [i, r]]));
  const out = [];
  CROPS.forEach((c) => {
    const base = { crop: c.code, crop_name: c.name, emoji: c.emoji, land_type: c.land_type };
    if (rank[c.code]) {
      const [i, r] = rank[c.code];
      if (r.demoted) out.push({ ...base, kind: "ph", reason: `심을 수는 있지만 ${LAND_TYPES[c.land_type]} 토지 흙(기존 작물 ${r.prev_crop} 기준 pH 약 ${r.soil_ph})이 알맞은 pH ${r.ph.min}~${r.ph.max}보다 ${r.ph.gap} 높아서 맨 아래(${i + 1}위)로 내렸어요.` });
      else if (i >= TOP_N) out.push({ ...base, kind: "low", reason: `심을 수는 있지만 예상 마진률이 ${Math.round(r.margin_rate)}%로, 추천 상위(${TOP_N}위 안)에 들지 못했어요. (${results.length}개 중 ${i + 1}위)` });
      return;
    }
    if (c.note) return out.push({ ...base, kind: "perennial", reason: `다년생 작물이라 날짜별 추천을 하지 않아요. ${c.note}` });
    if (!owned.includes(c.land_type)) return out.push({ ...base, kind: "land", reason: `${LAND_TYPES[c.land_type]} 토지에서만 재배할 수 있어요. 고른 토지: ${ownedTxt}` });
    const ws = c.cl.map((w) => `${w.name} ${tenDay(w.from)}~${tenDay(w.to)}`).join(", ");
    let next = null;
    for (let k = 1; k < 370 && !next; k++) {
      const d = addDays(start, k), nw = croppingOn(c, d);
      if (nw) next = [d, nw.name];
    }
    const tail = next ? ` 다음 심는 때: ${Number(next[0].slice(5, 7))}/${Number(next[0].slice(8))}부터(${next[1]})` : "";
    out.push({ ...base, kind: "season", reason: `지금(${month}월)은 심는 시기가 아니에요. ${LAND_TYPES[c.land_type]} ${ws}이에요.${tail}` });
  });
  return out;
}

/** 작물 정보 탭: 작형별 심는 기간·일수·10a당 수량·경영비 (GET /recommend/crops/{code}) */
export function mockCropInfo(code) {
  const c = BY[code];
  if (!c) throw Object.assign(new Error(`unknown crop: ${code}`), { status: 404 });
  return {
    crop: cropOut(c), note: c.note ?? null, marketable_rate: c.mk,
    rda: c.rda && { ...c.rda, revenue: c.rda.revenue * 1000, cost: c.rda.cost * 1000, income: c.rda.income * 1000 },
    croppings: c.cl.map((w) => ({
      name: w.name, plant_from: w.from, plant_to: w.to, days_to_harvest: w.dth, harvest_days: w.hd, storage_days: w.store,
      multi_harvest: w.hd > 30, yield_t_per_10a: w.yld, cost_per_10a: w.cost * 1e4, source: w.src,
    })),
    model_version: VERSION,
  };
}

export function mockRecommendCrops({ lands, start_date, region = "서울", market = null }) {
  // 토지마다 기존 작물 → 흙 pH 어림
  const soil = Object.fromEntries(lands.map((l) => [l.type, l.prev_crop ? { prev: l.prev_crop, ph: soilPhFromPrev(l.prev_crop) } : null]));
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
    if (w) return results.push(applyRegion(evaluate(c, w, start_date, a, today, rent[c.land_type]), region, market));
    let next = null;
    for (let k = 1; k < 370 && !next; k++) {
      const d = addDays(start_date, k), nw = croppingOn(c, d);
      if (nw) next = [d, nw.name];
    }
    unavailable.push({ ...base, reason: "심는 시기가 아니에요", next_plant_date: next?.[0] ?? null, next_cropping: next?.[1] ?? null });
  });
  // 기존 작물로 어림한 흙 pH 보다 낮은 pH 가 맞는 작물은 (pH 낮추기는 달 단위) 순이익과 상관없이 맨 아래로
  results.forEach((r) => {
    const sl = soil[r.land_type];
    r.prev_crop = sl?.prev ?? null; r.soil_ph = sl?.ph ?? null;
    r.ph = phCheck(r.crop, r.soil_ph); r.demoted = r.ph?.kind === "lower";
  });
  results.sort((x, y) => x.demoted - y.demoted || y.margin - x.margin);
  const { markets, none } = marketsInSido(region);
  return { start_date, region, markets, no_market: none, excluded: excludedReasons(results, lands, start_date), results, unavailable, model_version: VERSION };
}

export function mockPlantingDates({ crop, area_pyeong, land_rent = 0, machine_rent = 0, region = "서울", market = null }) {
  const c = BY[crop];
  if (!c) throw Object.assign(new Error(`unknown crop: ${crop}`), { status: 404 });
  if (c.note) return { crop: cropOut(c), note: c.note, best: null, top: [], points: [], model_version: VERSION };
  const today = todayIso();
  const points = Array.from({ length: 53 }, (_, k) => {
    const d = addDays(today, k * 7), w = croppingOn(c, d);
    return { plant_date: d, option: w ? applyRegion(evaluate(c, w, d, area_pyeong, today, { land: land_rent, machine: machine_rent }), region, market) : null };
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
  const points = Array.from({ length: 53 }, (_, k) => { // 12개월 (11-11, ml-api 와 같게)
    const d = addDays(today, k * 7), v = priceOn(c, d, today), e = errorPct(c.code, Math.max(1, daysBetween(today, d))) / 100;
    return { date: d, price: Math.round(v), lower: Math.round(v * (1 - e)), upper: Math.round(v * (1 + e)) };
  });
  return { crop: cropOut(c), points, model_version: VERSION };
}
