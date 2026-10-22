// 테스트 모드(live) 전용: 네이버 뉴스 검색 API 로 기사를 직접 받아 품목·분류를 붙인다.
// 수집기(collector/news)가 저장한 기사가 있으면 그것을 쓰고, 없으면 화면을 열 때 네이버에서 직접 받아 10분간 재사용한다.
// 실제 서비스에서는 수집기가 1시간마다 DB에 쌓고 Spring 이 읽어 준다 (명세 2-14).
// 주소는 /live/naver/... → Vite 개발 서버가 NAVER API HUB(naverapihub.apigw.ntruss.com)로 보내며 Client ID·Secret 헤더를 붙인다 (vite.config.js).
// HUB 뉴스 검색 응답의 items(title·originallink·link·description·pubDate)는 예전 개발자센터 API 와 같은 모양이다.
import RULES from "../../../../shared/news_rules.json";
import { liveGet } from "../client";
import { ITEMS } from "../../mocks/catalog";
import { categorize, isAgriNews } from "../../mocks/news";
import { findCrops, findItems } from "../../utils/itemMatch";

/** 언론사 이름 (API 가 주지 않아 원문 주소 도메인으로 붙인다. 없으면 도메인 그대로) — shared/news_rules.json */
const PRESS = RULES.press;

const TTL_MS = 10 * 60000;
const cache = new Map(); // 검색어 → { at, promise }

const ENTITIES = { "&quot;": '"', "&amp;": "&", "&lt;": "<", "&gt;": ">", "&apos;": "'", "&#39;": "'", "&nbsp;": " " };
const clean = (s) => String(s ?? "").replace(/<[^>]+>/g, "").replace(/&[a-z#0-9]+;/gi, (e) => ENTITIES[e] ?? e).trim();

function pressOf(url) {
  try {
    const host = new URL(url).hostname.replace(/^(www|m|news|n)\./, "");
    const key = Object.keys(PRESS).find((d) => host === d || host.endsWith(`.${d}`));
    return key ? PRESS[key] : host;
  } catch {
    return "";
  }
}

/** 검색어 하나의 최신 기사 (10분 캐시, 같은 검색어를 동시에 부르면 한 번만 요청) */
function search(query) {
  const hit = cache.get(query);
  if (hit && Date.now() - hit.at < TTL_MS) return hit.promise;
  const q = new URLSearchParams({ query, display: 50, sort: "date" });
  const promise = liveGet(`/live/naver/search/v1/news?${q}`).then((d) => {
    if (!Array.isArray(d?.items)) throw new Error(`네이버: ${d?.error?.message ?? d?.errorMessage ?? "응답 형식이 다릅니다"}`);
    return d.items;
  });
  promise.catch(() => cache.delete(query));
  cache.set(query, { at: Date.now(), promise });
  return promise;
}

/** 서버가 저장할 때 하는 일과 같게: 농업 기사만, 같은 기사 한 번만, 품목·분류 붙이기 */
// 같은 보도자료를 여러 언론사가 그대로 싣는 경우가 많아 제목(띄어쓰기·기호 뺀 것)이 같으면 한 번만
const titleKey = (t) => t.replace(/[^가-힣a-zA-Z0-9]/g, "");

function toRows(raw) {
  const seen = new Set();
  const rows = [];
  for (const a of [...raw].sort((x, y) => new Date(y.pubDate) - new Date(x.pubDate))) {
    const url = a.originallink || a.link;
    const title = clean(a.title);
    if (!url || seen.has(url) || seen.has(titleKey(title))) continue;
    seen.add(url);
    seen.add(titleKey(title));
    const summary = clean(a.description);
    if (!isAgriNews(title, summary)) continue;
    rows.push({
      id: url,
      title,
      summary,
      press: pressOf(url),
      url,
      published_at: new Date(a.pubDate).toISOString(),
      items: findItems(`${title} ${summary}`),
      crops: findCrops(`${title} ${summary}`),
      category: categorize(title, summary),
    });
  }
  return rows;
}

/** 검색어: 기본 + 품목 16개 + 품목 밖 작물 (수집기와 같음) */
const QUERIES = [
  ...RULES.queries.base,
  ...(RULES.queries.add_items ? ITEMS.map((i) => i.name) : []),
  ...(RULES.queries.add_other_crops ? Object.values(RULES.other_crops).map((c) => c.name) : []),
];

/** 수집기가 저장한 기사 (collector/news/data/news.json). 없으면 null → 네이버 직접 호출 */
async function collectedNews() {
  const res = await fetch("/live/collected-news").catch(() => null);
  if (!res?.ok) return null;
  const data = await res.json();
  return { rows: data.articles, fetchedAt: new Date(data.updated_at) };
}

/**
 * 기사 묶음: 기본 검색어 + 품목 16개 + 품목 밖 작물. 검색·필터는 이 안에서만 한다 (실제 서비스도 저장된 기사 안에서만 찾음)
 * @returns {Promise<{rows: object[], fetchedAt: Date}>}
 */
export async function liveNewsPool() {
  const collected = await collectedNews();
  if (collected) return collected;
  const queries = QUERIES;
  const lists = [];
  // 네이버 초당 호출 제한 대비 4개씩
  for (let i = 0; i < queries.length; i += 4) lists.push(...(await Promise.all(queries.slice(i, i + 4).map(search))));
  const at = Math.min(...queries.map((q) => cache.get(q)?.at ?? Date.now()));
  return { rows: toRows(lists.flat()), fetchedAt: new Date(at) };
}
