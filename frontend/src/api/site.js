// 사이트 설정 (11-17) — 관리자 사이트 '사이트 설정'에서 넣은 공지 띠 · 점검 안내 · 팀 소개 · 연락처 (Spring GET /api/site, 누구나)
// 서버에 못 닿거나 예전 서버면 빈 값 → 띠·팀 소개가 안 보일 뿐 화면은 그대로
import { useEffect, useState } from "react";

const EMPTY = { notice: "", maintenance: "", team: [], contact: { email: "", phone: "", hours: "" } };
let cache = null; // { at, promise }

export function getSite() {
  if (cache && Date.now() - cache.at < 60000) return cache.promise;
  const promise = fetch("/api/site")
    .then((r) => (r.ok ? r.json() : EMPTY))
    .then((d) => ({ ...EMPTY, ...d, team: Array.isArray(d?.team) ? d.team : [], contact: { ...EMPTY.contact, ...d?.contact } }))
    .catch(() => EMPTY);
  cache = { at: Date.now(), promise };
  return promise;
}

export function useSite() {
  const [site, setSite] = useState(EMPTY);
  useEffect(() => {
    let on = true;
    getSite().then((s) => on && setSite(s));
    return () => { on = false; };
  }, []);
  return site;
}

/** 관리자가 숨긴 기사 주소들 (1분 기억). 못 불러오면 빈 목록 = 아무것도 숨기지 않음 */
let hiddenCache = null;
export function getHiddenNewsUrls() {
  if (hiddenCache && Date.now() - hiddenCache.at < 60000) return hiddenCache.promise;
  const promise = fetch("/api/news/hidden").then((r) => (r.ok ? r.json() : [])).then((a) => new Set(Array.isArray(a) ? a : [])).catch(() => new Set());
  hiddenCache = { at: Date.now(), promise };
  return promise;
}
export const clearHiddenNewsCache = () => { hiddenCache = null; };
