// 통합 검색 (Spring 담당). 지금은 품목·경매·게시글·공지·뉴스 가짜 데이터를 화면 쪽에서 모아 찾는다.
// Spring 이 생기면 searchAll 안쪽을 GET /api/search?q= 한 번으로 바꾼다. 명세: docs/06_api_spec.md 2-13
import { fake } from "./client";
import { getNotices } from "./admin";
import { displayStatus } from "./auction";
import { getPosts } from "./board";
import { getNews } from "./news";
import { ITEMS } from "../mocks/catalog";
import { mockCropList } from "../mocks/recommend";
import { auctionsDb } from "../mocks/auctions";
import { AUCTION_ENABLED } from "../features";
import { itemOfQuery, suggestItemName } from "../utils/itemMatch";

const PUBLIC_STATUS = ["진행중", "낙찰", "유찰"];

// 작물 추천에 있는 작물 (ml-api /recommend/crops 와 같은 목록). 검색어가 작물 이름이면 "심는 날 추천"으로 바로 갈 수 있게
const CROPS = mockCropList();
export const RECOMMEND_AREA = 600; // 검색에서 작물 추천으로 갈 때 기본 평수

/** 작물 추천 주소 (작물로 심을 날짜 고르기 탭) */
export const recommendLink = (code, area = RECOMMEND_AREA) => `/recommend?tab=crop&crop=${code}&area=${area}`;

/** 검색어에 걸린 작물: 이름이 같으면 맨 앞, 그다음 이름이 검색어로 시작하거나 검색어를 포함하는 작물 */
function findCrops(word, code) {
  if (!word) return [];
  const score = (c) => (c.name === word || c.code === code ? 0 : c.name.startsWith(word) ? 1 : c.name.includes(word) ? 2 : 9);
  return CROPS.map((c) => [score(c), c]).filter(([s]) => s < 9).sort((a, b) => a[0] - b[0]).map(([, c]) => c);
}

/** 검색어에 걸린 경매 (진행 중 먼저, 그다음 마감 임박 순) */
function findAuctions(word, item) {
  if (!AUCTION_ENABLED) return [];
  return auctionsDb
    .all()
    .map(({ bids, ...a }) => ({ ...a, shown_status: displayStatus(a) }))
    .filter((a) => PUBLIC_STATUS.includes(a.shown_status))
    .filter((a) => `${a.title} ${a.origin}`.toLowerCase().includes(word) || (item && a.item === item))
    .sort((a, b) => ended(a) - ended(b) || new Date(a.ends_at) - new Date(b.ends_at));
}

const ended = (a) => (a.shown_status === "진행중" ? 0 : 1);

/**
 * 통합 검색. 검색어가 품목 이름(별칭 포함)이면 그 품목 정보도 함께.
 * @returns {Promise<{q: string, item: object|null, auctions: object[], posts: {rows: object[], total: number}, notices: object[], news: {rows: object[], total: number, updated_at: string}, total: number, suggestion: string|null}>}
 */
export async function searchAll(q, { newsSize = 4 } = {}) {
  const word = q.trim().toLowerCase();
  const code = itemOfQuery(q);
  const item = ITEMS.find((i) => i.code === code) ?? null;
  const [posts, notices, news] = await Promise.all([
    getPosts({ q: word }),
    getNotices(),
    getNews({ q: word, qItem: code, size: newsSize }),
  ]);
  const auctions = findAuctions(word, code);
  const crops = findCrops(word, code);
  const hitNotices = notices.filter((n) => `${n.title} ${n.body}`.toLowerCase().includes(word));
  const total = (item ? 1 : 0) + crops.length + auctions.length + posts.total + hitNotices.length + news.total;
  return {
    q: q.trim(),
    item,
    crops,
    auctions,
    posts: { rows: posts.rows, total: posts.total },
    notices: hitNotices,
    news: { rows: news.rows, total: news.total, updated_at: news.updated_at },
    total,
    suggestion: total === 0 ? suggestItemName(q) : null,
  };
}

/** 검색창 자동완성: 종류마다 몇 개씩만 */
export async function suggest(q) {
  const word = q.trim().toLowerCase();
  if (!word) return null;
  const code = itemOfQuery(q);
  // 한 글자만 쳤을 때도 "사" → 사과 처럼 이름 앞부분으로 품목을 찾는다
  const items = ITEMS.filter((i) => i.code === code || i.name.startsWith(word)).slice(0, 3);
  const [posts, news] = await Promise.all([getPosts({ q: word }), getNews({ q: word, qItem: code, size: 2 })]);
  return fake(
    {
      items,
      crops: findCrops(word, code).slice(0, 2),
      auctions: findAuctions(word, code).filter((a) => a.shown_status === "진행중").slice(0, 2),
      posts: posts.rows.slice(0, 2),
      news: news.rows.slice(0, 2),
    },
    0,
  );
}

// ── 최근 검색어 (이 브라우저에만 저장) ──
const RECENT_KEY = "farmbid-recent-search";

export function recentSearches() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY)) ?? [];
  } catch {
    return [];
  }
}

export function saveRecentSearch(q) {
  const list = [q, ...recentSearches().filter((x) => x !== q)].slice(0, 5);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* 저장소를 못 쓰면 무시 */
  }
  return list;
}

export function removeRecentSearch(q) {
  const list = recentSearches().filter((x) => x !== q);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* 무시 */
  }
  return list;
}
