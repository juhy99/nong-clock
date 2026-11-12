// 시세 가짜 데이터 (Spring 담당 API 가 생기기 전까지 사용).
// 응답 모양은 docs/06_api_spec.md 2-1, 2-15 와 같다.
// 가격은 (품목·시장·등급·날짜)마다 같은 규칙으로 만들어서, 어느 화면에서 보든 숫자가 맞는다.
// 기본 기준(전국 도매시장 · 상 등급)의 최근 거래일 가격 = catalog 의 BASE_PRICE (= AI 예측의 "오늘" 가격).
import { addDays, daysBetween, seeded, todayIso } from "../utils/format";
import { BASE_PRICE, ITEMS } from "./catalog";
import { IN50 } from "./items50";
import MARKET_DATA from "../../../shared/markets.json";

// 시장별 물량 1위 품목 (홈 지도 "시세 보기"에서 관심 품목이 없을 때 여는 품목).
// 실제 API 는 최근 거래일 기준. 가짜 데이터는 팀 일별 자료의 2024년 10월 물량 1위 (2025-10 ~ 2026-03 자료가 비어 있음)
const TOP_ITEM = {
  110001: "onion", 110008: "radish", 210001: "onion", 210009: "onion", 220001: "onion", 230001: "onion", 230003: "napa_cabbage",
  240001: "radish", 240004: "radish", 250001: "radish", 250003: "onion", 310101: "radish", 310401: "onion", 310901: "napa_cabbage",
  311201: "onion", 320101: "radish", 320201: "mandarin", 320301: "radish", 330101: "mandarin", 330201: "mandarin", 340101: "radish",
  350101: "radish", 350301: "onion", 350402: "sweet_potato", 360301: "radish", 370101: "mandarin", 370401: "apple", 371501: "onion",
  380101: "mandarin", 380201: "radish", 380303: "radish", 380401: "mandarin",
};
// 최근 1년(2025-09 ~ 2026-08) 거래 기록이 없는 품목
const NOT_TRADED = {
  370401: ["button_mushroom", "enoki_mushroom", "green_onion", "king_oyster_mushroom", "radish"],
  371501: ["button_mushroom", "enoki_mushroom", "king_oyster_mushroom"],
};

// 공영 도매시장 32곳 + 전국 평균. 목록의 기준은 shared/markets.json 한 파일 (ml-api/app/core/markets.py 도 같은 파일을 읽음)
// code = 정산 자료의 도매시장코드, 위도·경도는 대략값 (홈 지도 표시용)
export const MARKETS = [
  { code: "national", name: "전국 도매시장 평균" },
  ...MARKET_DATA.markets.map(({ code, name, sido, sigungu, lat, lon }) => ({
    code, name, sido, sigungu, lat, lon,
    top_item: TOP_ITEM[code],
    items: ITEMS.map((i) => i.code).filter((c) => !NOT_TRADED[code]?.includes(c)),
  })),
];

// 등급 코드는 DB price_daily.grade 와 같다 (ALL = 등급 구분 없이 거래량을 반영한 평균)
const GRADE_FACTOR = { SPECIAL: 1.17, HIGH: 1, MID: 0.86, LOW: 0.7, ALL: 0.93 };

// 품목별 주산지 (출하지역 1위가 되기 쉬운 시·도)
const MAIN_ORIGIN = {
  potato: "강원", onion: "전남", carrot: "제주", apple: "경북", watermelon: "충북", napa_cabbage: "강원",
  radish: "강원", tomato: "충남", cabbage: "제주", sweet_potato: "전남", button_mushroom: "충남", pear: "전남",
  king_oyster_mushroom: "경남", green_onion: "전남", mandarin: "제주", enoki_mushroom: "경북",
};
const ORIGIN_POOL = ["경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];
const RETAIL_MARKUP = { 근채류: 1.9, 서류: 1.9, 조미채소류: 2.1, 과일류: 1.6, 견과류: 1.6, 과채류: 1.7, 엽경채류: 2.4, 양채류: 2.2, 산채류: 2.2, 버섯류: 1.5, 두류: 1.7, 잡곡: 1.7 };

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

export const marketFactor = (item, market) => (market === "national" ? 1 : 0.9 + noise(`m|${item}|${market}`) * 0.2);

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
  const items = ITEMS.filter((i) => IN50.has(i.code)).map((info) => { // [샘플] 50품목만
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

// ── [샘플 11-12] 시세 화면 맨 아래 "도매시장별 가격 · 산지공판장 가격" (고른 시장과 상관없이 품목·품종만) ──
// 실제는 경매원장 최근 12달 집계: 시장별 평균 경락가(총 금액 ÷ 총 물량)와 그 품목 전체 물량 중 그 시장 몫.
// [이름, 시·도, 그래프용 짧은 이름]
const AUCTION_HOUSES = [
  ["풍기농협 공판장", "경북", "풍기"], ["안동농협 공판장", "경북", "안동"], ["영천농협 공판장", "경북", "영천"], ["예산능금농협 공판장", "충남", "예산능금"],
  ["논산원예농협 공판장", "충남", "논산원예"], ["목포원예농협 공판장", "전남", "목포원예"], ["무안농협 공판장", "전남", "무안"], ["해남농협 공판장", "전남", "해남"],
  ["전주농협 공판장", "전북", "전주"], ["군산원예농협 공판장", "전북", "군산원예"], ["남원원예농협 공판장", "전북", "남원원예"], ["거창사과원예농협 공판장", "경남", "거창사과"],
  ["창녕농협 공판장", "경남", "창녕"], ["충주사과원예농협 공판장", "충북", "충주사과"], ["평창농협 공판장", "강원", "평창"], ["제주시농협 산물공판장", "제주", "제주시"],
];
const r1 = (n) => Math.round(n * 10) / 10;

/** 도매시장별 최근 12달 평균 경락가 · 물량 몫 (물량 많은 시장 8곳, 몫 큰 순) + 물량 가중 평균(전체 시장) */
export function mockMarketShare(item) {
  const ms = MARKETS.filter((m) => m.code !== "national" && m.items.includes(item));
  const w = ms.map((m) => ({ m, w: 0.2 + noise(`ms|${item}|${m.code}`) ** 2 * 3 }));
  const total = w.reduce((a, x) => a + x.w, 0);
  const rows = w.map(({ m, w: x }) => ({
    market: m.name, code: m.code,
    price: Math.round(BASE_PRICE[item] * marketFactor(item, m.code) * (0.9 + noise(`mp|${item}|${m.code}`) * 0.2)),
    share_pct: r1((x / total) * 100),
  })).sort((a, b) => b.share_pct - a.share_pct);
  const vw = rows.reduce((a, r) => a + r.price * r.share_pct, 0) / rows.reduce((a, r) => a + r.share_pct, 0);
  return { item, period: "최근 12달", markets: rows.slice(0, 8), market_count: rows.length, weighted_avg: Math.round(vw), sample: true };
}

/** 산지공판장 최근 12달 평균 경락가 · 지난 3년(23~25년) 평균 · 산지 물량 몫 (몫 큰 곳 8곳) */
export function mockAuctionHouses(item) {
  const pick = AUCTION_HOUSES.map(([name, sido, short]) => ({ name, sido, short, w: noise(`ah|${item}|${name}`) ** 3 }))
    .sort((a, b) => b.w - a.w).slice(0, 8);
  const total = pick.reduce((a, x) => a + x.w, 0) / 0.85; // 나머지 15% 는 목록 밖 공판장
  return {
    item, period: "최근 12달", past: "23~25년",
    houses: pick.map((h) => {
      const now = Math.round(BASE_PRICE[item] * (0.85 + noise(`ahp|${item}|${h.name}`) * 0.35));
      return { name: h.name, short: h.short, sido: h.sido, price: now, past_price: Math.round(now * (0.82 + noise(`ahq|${item}|${h.name}`) * 0.2)), share_pct: r1((h.w / total) * 100) };
    }),
    sample: true,
  };
}
