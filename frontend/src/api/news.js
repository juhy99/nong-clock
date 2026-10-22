// 농업 뉴스. 수집기(collector/news)가 1시간마다 네이버 뉴스 검색 API 로 기사를 모아 품목·분류를 붙여 저장하고, 화면은 저장된 기사만 읽는다.
// (네이버 API 키는 서버에만 둔다. 화면이 네이버를 직접 부르지 않는다.) 명세: docs/06_api_spec.md 2-14
// 기사 출처: VITE_NEWS_URL(서버에 모인 기사 파일) → 테스트 모드(VITE_DATA_SOURCE=live, api/live/naverNews.js) → 가짜 예시 기사
// Spring 이 생기면 newsPool 대신 GET /api/news 로 바꾼다 (검색·쪽 나누기를 서버가 함).
import { ApiError, DATA_SOURCE, NEWS_URL, fake } from "./client";
import { liveNewsPool } from "./live/naverNews";
import { ITEMS } from "../mocks/catalog";
import { NEWS_CATEGORIES, labelNews } from "../mocks/news";
import { OTHER_CROPS, cropOfQuery } from "../utils/itemMatch";

export { NEWS_CATEGORIES };
export const NEWS_REFRESH_MINUTES = 60;
export const NEWS_PAGE_SIZE = 15;

/** 가장 최근 수집 시각 (가짜: 매시 정각에 모았다고 본다) */
function lastFetchedAt(now = new Date()) {
  const d = new Date(now);
  d.setMinutes(0, 0, 0);
  return d;
}

const SERVER_TTL_MS = 60000;
let serverCache = null; // { at, promise }

/** 서버에 모인 기사 파일 (1분 캐시, 같은 때 여러 번 불러도 한 번만 받음) */
function serverNewsPool() {
  if (serverCache && Date.now() - serverCache.at < SERVER_TTL_MS) return serverCache.promise;
  const promise = fetch(NEWS_URL, { cache: "no-cache" })
    .then((res) => {
      if (!res.ok) throw new ApiError(res.status === 404 ? "서버에 아직 수집한 기사가 없어요" : `서버 뉴스를 불러오지 못했어요 (HTTP ${res.status})`, res.status);
      return res.json();
    }, () => {
      throw new ApiError("서버에 연결할 수 없어요 (서버 주소·접속 확인)", 0);
    })
    .then((d) => ({ rows: d.articles, fetchedAt: new Date(d.updated_at), real: true }));
  promise.catch(() => (serverCache = null));
  serverCache = { at: Date.now(), promise };
  return promise;
}

/** 기사 묶음과 수집 시각. real: 실제 기사(서버 수집·테스트 모드) / 아니면 예시 기사(매시 정각 수집으로 가정) */
async function newsPool() {
  if (NEWS_URL) return serverNewsPool();
  if (DATA_SOURCE === "live") return { ...(await liveNewsPool()), real: true };
  const fetchedAt = lastFetchedAt();
  return { rows: labelNews(fetchedAt.getTime()), fetchedAt, real: false };
}

const newestFirst = (a, b) => new Date(b.published_at) - new Date(a.published_at);
const itemInfo = (code) => ITEMS.find((i) => i.code === code);

/** 화면에 품목 이름·이모지를 바로 쓰도록 붙여 준다 (Spring 응답도 같은 모양 제안) */
const withTags = (n) => ({
  ...n,
  item_tags: n.items.map((c) => ({ item: c, name: itemInfo(c)?.name ?? c, emoji: itemInfo(c)?.emoji ?? "🧺" })),
  // 16개 품목 밖 작물 (시세·예측 화면이 없어 링크 없이 표시)
  crop_tags: (n.crops ?? []).map((c) => ({ crop: c, name: OTHER_CROPS[c]?.name ?? c, emoji: OTHER_CROPS[c]?.emoji ?? "🌱" })),
});

/**
 * 뉴스 목록 (최신순)
 * @param {{category?: string, item?: string, items?: string[], q?: string, qItem?: string, page?: number, size?: number}} opts
 *   item: 품목 하나, items: 이 중 하나라도 걸린 기사 (내 관심 품목만),
 *   q: 제목·요약 검색, qItem: 검색어가 가리키는 품목 (예: "부사" → apple 태그 기사도 함께)
 *   검색어가 품목 밖 작물이면 그 작물 태그 기사도 함께 (예: "포도" → 샤인머스캣 기사)
 * @returns {Promise<{rows: object[], total: number, page: number, pages: number, updated_at: string, next_update_at: string}>}
 */
export async function getNews({ category = "", item = "", items = null, q = "", qItem = null, page = 1, size = NEWS_PAGE_SIZE } = {}) {
  const word = q.trim().toLowerCase();
  const qCrop = word ? cropOfQuery(word) : null;
  const { rows: pool, fetchedAt, real } = await newsPool();
  const rows = pool
    .filter((n) => !category || n.category === category)
    .filter((n) => !item || n.items.includes(item))
    .filter((n) => !items || n.items.some((c) => items.includes(c)))
    .filter((n) => !word || `${n.title} ${n.summary}`.toLowerCase().includes(word) || (qItem && n.items.includes(qItem)) || (qCrop && n.crops?.includes(qCrop)))
    .sort(newestFirst);
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const cur = Math.min(Math.max(1, page), pages);
  const res = {
    rows: rows.slice((cur - 1) * size, cur * size).map(withTags),
    total: rows.length,
    page: cur,
    pages,
    updated_at: fetchedAt.toISOString(),
    next_update_at: new Date(fetchedAt.getTime() + NEWS_REFRESH_MINUTES * 60000).toISOString(),
  };
  return real ? res : fake(res);
}

/** 최근 N일 기사에 많이 나온 품목 (기사 수 순) */
export async function getNewsTrend({ days = 7, limit = 5 } = {}) {
  const since = Date.now() - days * 86400000;
  const counts = {};
  const { rows: pool, real } = await newsPool();
  for (const n of pool)
    if (new Date(n.published_at) >= since) n.items.forEach((c) => (counts[c] = (counts[c] ?? 0) + 1));
  const rows = Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([code, count]) => {
      const info = itemInfo(code);
      return { item: code, name: info?.name ?? code, emoji: info?.emoji ?? "🧺", count };
    });
  return real ? rows : fake(rows, 150);
}
