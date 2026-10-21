// 시세 가짜 데이터 (Spring 담당 API 가 생기기 전까지 사용).
// 응답 모양은 docs/06_api_spec.md 2-1, 2-15 와 같다.
// 가격은 (품목·시장·등급·날짜)마다 같은 규칙으로 만들어서, 어느 화면에서 보든 숫자가 맞는다.
// 기본 기준(전국 도매시장 · 상 등급)의 최근 거래일 가격 = catalog 의 BASE_PRICE (= AI 예측의 "오늘" 가격).
import { addDays, daysBetween, seeded, todayIso } from "../utils/format";
import { BASE_PRICE, ITEMS } from "./catalog";

// 도매시장 32곳 + 전국 평균. ⚠️ 실제 목록은 데이터 담당(market 테이블)과 맞출 것
export const MARKETS = [
  ["national", "전국 도매시장 평균"],
  ["garak", "서울가락"], ["gangseo", "서울강서"], ["busan_eomgung", "부산엄궁"], ["busan_banyeo", "부산반여"],
  ["daegu_bukbu", "대구북부"], ["incheon_guwol", "인천구월"], ["incheon_samsan", "인천삼산"], ["gwangju_gakhwa", "광주각화"],
  ["gwangju_seobu", "광주서부"], ["daejeon_ojeong", "대전오정"], ["daejeon_noeun", "대전노은"], ["ulsan", "울산"],
  ["suwon", "수원"], ["anyang", "안양"], ["ansan", "안산"], ["guri", "구리"], ["chuncheon", "춘천"], ["wonju", "원주"],
  ["gangneung", "강릉"], ["cheongju", "청주"], ["chungju", "충주"], ["cheonan", "천안"], ["jeonju", "전주"],
  ["iksan", "익산"], ["jeongeup", "정읍"], ["suncheon", "순천"], ["pohang", "포항"], ["andong", "안동"],
  ["gumi", "구미"], ["changwon_palyong", "창원팔용"], ["changwon_naeseo", "창원내서"], ["jinju", "진주"],
].map(([code, name]) => ({ code, name }));

// 등급 코드는 DB price_daily.grade 와 같다 (ALL = 등급 구분 없이 거래량을 반영한 평균)
const GRADE_FACTOR = { SPECIAL: 1.17, HIGH: 1, MID: 0.86, LOW: 0.7, ALL: 0.93 };

// 품목별 주산지 (출하지역 1위가 되기 쉬운 시·도)
const MAIN_ORIGIN = {
  potato: "강원", onion: "전남", carrot: "제주", apple: "경북", watermelon: "충북", napa_cabbage: "강원",
  radish: "강원", tomato: "충남", cabbage: "제주", sweet_potato: "전남", button_mushroom: "충남", pear: "전남",
  king_oyster_mushroom: "경남", green_onion: "전남", mandarin: "제주", enoki_mushroom: "경북",
};
const ORIGIN_POOL = ["경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
const RETAIL_MARKUP = { 근채류: 1.9, 조미채소: 2.1, 과일류: 1.6, 과채류: 1.7, 엽채류: 2.4, 버섯류: 1.5 };

const noise = (key) => seeded(key)();
const dayNo = (iso) => daysBetween("2020-01-01", iso);

/** 거래일 여부 (KAMIS 처럼 토·일 제외. 공휴일은 단순화를 위해 생략) */
const isTradingDay = (iso) => ![0, 6].includes(new Date(`${iso}T00:00:00`).getDay());

/** iso 와 같거나 그 전의 가장 가까운 거래일 (오늘보다 뒤면 오늘 기준) */
export function latestTradingDay(iso) {
  let d = !iso || iso > todayIso() ? todayIso() : iso;
  while (!isTradingDay(d)) d = addDays(d, -1);
  return d;
}

/** endIso 까지의 거래일 count 개 (오래된 날짜 → 최근) */
function tradingDays(endIso, count) {
  const days = [];
  let d = latestTradingDay(endIso);
  while (days.length < count) {
    if (isTradingDay(d)) days.unshift(d);
    d = addDays(d, -1);
  }
  return days;
}

/** 품목별 가격 흐름 (날짜마다 고정값) */
function wave(item, iso, smooth = false) {
  const n = dayNo(iso);
  const r = seeded(`wave|${item}`);
  const a = r() * 6, b = r() * 6;
  const w = 1 + 0.07 * Math.sin(n / 9 + a) + 0.04 * Math.sin(n / 3.1 + b);
  return smooth ? 1 + (w - 1) * 0.3 : w + 0.03 * (noise(`d|${item}|${iso}`) - 0.5);
}

const marketFactor = (item, market) => (market === "national" ? 1 : 0.9 + noise(`m|${item}|${market}`) * 0.2);

/** 해당 날짜에 그 등급 거래가 없었으면 true (하 등급은 자주, 특 등급은 가끔 비어 있다) */
function noTrade(item, market, grade, iso) {
  const r = noise(`nt|${item}|${market}|${grade}|${iso}`);
  if (grade === "LOW") return r < (market === "national" ? 0.3 : 0.45);
  if (grade === "SPECIAL") return r < (market === "national" ? 0.06 : 0.15);
  if (grade === "HIGH") return market !== "national" && r < 0.04;
  return false;
}

/** 도매가 (원/kg). 거래가 없으면 null */
function wholesale(item, market, grade, iso) {
  if (noTrade(item, market, grade, iso)) return null;
  const anchor = latestTradingDay();
  let p = BASE_PRICE[item] * GRADE_FACTOR[grade] * marketFactor(item, market) * (wave(item, iso) / wave(item, anchor));
  if (!(market === "national" && grade === "HIGH")) p *= 1 + 0.03 * (noise(`g|${item}|${market}|${grade}|${iso}`) - 0.5);
  return Math.round(p);
}

/** 전국 소매가 (원/kg). 시장·등급 구분 없음 */
function retail(item, iso) {
  const cat = ITEMS.find((i) => i.code === item)?.category;
  const anchor = latestTradingDay();
  return Math.round(BASE_PRICE[item] * (RETAIL_MARKUP[cat] ?? 1.8) * (wave(item, iso, true) / wave(item, anchor, true)) / 10) * 10;
}

/** 하루 반입량 (톤) */
function dayVolume(item, market, iso) {
  const base = 120 + noise(`v|${item}`) * 480;
  const share = market === "national" ? 1 : 0.04 + noise(`vs|${item}|${market}`) * 0.12;
  return base * share * (0.7 + 0.6 * noise(`vd|${item}|${market}|${iso}`));
}

const pctOf = (now, prev) => (now == null || !prev ? null : Math.round(((now - prev) / prev) * 1000) / 10);

/** 오늘의 시세 = 전국 도매시장 · 상 등급 (홈·시세 띠·검색·마이페이지) + 전국 소매가 */
export function mockTodayPrices() {
  const [compared_date, base_date] = tradingDays(todayIso(), 2);
  const items = ITEMS.map((info) => {
    const price = wholesale(info.code, "national", "HIGH", base_date);
    const prev = wholesale(info.code, "national", "HIGH", compared_date);
    const retail_price = retail(info.code, base_date);
    return {
      item: info.code, name: info.name, emoji: info.emoji, category: info.category,
      price, prev_price: prev, change: price - prev, change_pct: pctOf(price, prev),
      retail_price, margin_pct: Math.round(((retail_price - price) / price) * 100),
    };
  });
  return { base_date, compared_date, market: "national", grade: "HIGH", unit: "kg", items };
}

/** 등급별 오늘 가격 + 최근 5거래일 (시세 › 등급별 가격 한눈에 보기) */
export function mockGradePrices(item, { market = "national", date } = {}) {
  const days = tradingDays(date || todayIso(), 5);
  const base = days.at(-1), prev = days.at(-2), yearAgo = latestTradingDay(addDays(base, -364));
  const card = (fn) => {
    const price = fn(base), before = fn(prev);
    return {
      price, prev_price: before,
      change: price != null && before != null ? price - before : null,
      change_pct: before != null ? pctOf(price, before) : null,
      year_ago_pct: pctOf(price, fn(yearAgo)),
      points: days.map((d) => ({ date: d, price: fn(d) })),
    };
  };
  return {
    item, market, base_date: base, compared_date: prev, unit: "kg",
    grades: Object.keys(GRADE_FACTOR).map((grade) => ({ grade, ...card((d) => wholesale(item, market, grade, d)) })),
    retail: card((d) => retail(item, d)),
  };
}

/** 날짜별 가격 추이 (한 등급) + 최고·최저·반입량 + 전국 소매가 */
export function mockPriceHistory(item, { market = "national", grade = "HIGH", date, days = 8 } = {}) {
  const list = tradingDays(date || todayIso(), days + 1);
  const points = list.slice(1).map((d, i) => {
    const price = wholesale(item, market, grade, d);
    const before = wholesale(item, market, grade, list[i]);
    const r = seeded(`hl|${item}|${market}|${grade}|${d}`);
    return {
      date: d, price,
      change: price != null && before != null ? price - before : null,
      change_pct: before != null ? pctOf(price, before) : null,
      high: price == null ? null : Math.round(price * (1 + 0.02 + r() * 0.05)),
      low: price == null ? null : Math.round(price * (1 - 0.02 - r() * 0.05)),
      volume_t: Math.round(dayVolume(item, market, d)),
      retail: retail(item, d),
    };
  });
  return { item, market, grade, unit: "kg", points };
}

/** 품목의 출하지역(시·도) 목록과 비중 (key 마다 조금씩 달라진다) */
function originShares(item, key) {
  const main = MAIN_ORIGIN[item] ?? "경기";
  const r = seeded(`os|${item}`);
  const others = ORIGIN_POOL.filter((o) => o !== main).sort(() => r() - 0.5).slice(0, 5);
  const k = seeded(`osk|${item}|${key}`);
  const weights = [main, ...others].map((region, i) => ({ region, w: (i === 0 ? 2.2 : 1 / (i + 0.5)) * (0.75 + k() * 0.5) }));
  const sum = weights.reduce((s, x) => s + x.w, 0);
  return weights.map((x) => ({ region: x.region, share: x.w / sum })).sort((a, b) => b.share - a.share);
}

/** 출하지역별 가격·반입량 (시세 › 출하지역별 가격). 평균(ALL) 등급 기준 */
export function mockOriginPrices(item, { market = "national", date } = {}) {
  const [prev, base] = tradingDays(date || todayIso(), 2);
  const vol = dayVolume(item, market, base);
  const avg = wholesale(item, market, "ALL", base), avgPrev = wholesale(item, market, "ALL", prev);
  const regions = originShares(item, base).map(({ region, share }) => {
    const f = 0.9 + noise(`op|${item}|${region}`) * 0.2;
    const price = Math.round(avg * f * (1 + 0.04 * (noise(`opd|${item}|${region}|${base}`) - 0.5)));
    const before = Math.round(avgPrev * f * (1 + 0.04 * (noise(`opd|${item}|${region}|${prev}`) - 0.5)));
    const r = seeded(`ohl|${item}|${region}|${base}`);
    return {
      region, price, change: price - before, change_pct: pctOf(price, before),
      high: Math.round(price * (1 + r() * 0.06)), low: Math.round(price * (1 - r() * 0.06)),
      volume_t: Math.max(1, Math.round(vol * share)),
    };
  });
  return { item, market, base_date: base, compared_date: prev, unit: "kg", regions };
}

const DEKAD = ["상순", "중순", "하순"];
/** 날짜가 속한 순(10일)의 첫날 */
function dekadStart(iso) {
  const [y, m, d] = iso.split("-");
  return `${y}-${m}-${d <= "10" ? "01" : d <= "20" ? "11" : "21"}`;
}
const dekadLabel = (start) => `${Number(start.slice(5, 7))}월 ${DEKAD[start.slice(8) === "01" ? 0 : start.slice(8) === "11" ? 1 : 2]}`;

/** 순(10일) 단위 출하지역별 반입량 (시세 › 반입 동향). 이번 순은 날짜까지의 누적 */
export function mockVolumeTrend(item, { market = "national", date, periods = 9 } = {}) {
  const end = latestTradingDay(date || todayIso());
  const starts = [dekadStart(end)];
  while (starts.length < periods) starts.unshift(dekadStart(addDays(starts[0], -1)));
  const rows = starts.map((start, i) => {
    const stop = i === starts.length - 1 ? end : addDays(starts[i + 1], -1);
    let total = 0;
    for (let d = start; d <= stop; d = addDays(d, 1)) if (isTradingDay(d)) total += dayVolume(item, market, d);
    const shares = originShares(item, start);
    const top = shares.slice(0, 2).map((s) => ({ region: s.region, volume_t: Math.round(total * s.share) }));
    total = Math.round(total);
    return { period: dekadLabel(start), start, end: stop, top1: top[0], top2: top[1], others_t: total - top[0].volume_t - top[1].volume_t, total_t: total };
  });
  const now = rows.at(-1), before = rows.at(-2);
  // 이번 순은 아직 진행 중일 수 있으니, 지난 순도 같은 거래일 수까지만 더해서 비교한다
  const count = (from, to) => { let n = 0; for (let d = from; d <= to; d = addDays(d, 1)) if (isTradingDay(d)) n += 1; return n; };
  let nDays = count(now.start, now.end), prevSame = 0;
  for (let d = before.start; d <= before.end && nDays > 0; d = addDays(d, 1)) if (isTradingDay(d)) { prevSame += dayVolume(item, market, d); nDays -= 1; }
  prevSame = Math.round(prevSame);
  const yoy = (region) => Math.round((noise(`yoy|${item}|${region}|${now.start}`) * 50 - 20) * 10) / 10;
  return {
    item, market, unit: "톤", periods: rows,
    summary: {
      period: now.period,
      top: [now.top1, now.top2].map((t) => ({ ...t, share_pct: Math.round((t.volume_t / now.total_t) * 100), year_ago_pct: yoy(t.region) })),
      others_t: now.others_t,
      total_t: now.total_t,
      change_t: now.total_t - prevSame,
      change_pct: pctOf(now.total_t, prevSame),
    },
  };
}

/** 시장별 오늘 가격 (통합 검색 › 시장별 오늘 시세). 상 등급 */
export function mockMarketCompare(code) {
  const base = latestTradingDay();
  const markets = MARKETS.slice(1, 6).map((m) => ({ market: m.name, price: wholesale(code, m.code, "HIGH", base) ?? wholesale(code, m.code, "ALL", base) }));
  return { item: code, unit: "kg", markets };
}
