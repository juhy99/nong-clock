// 개발자(관리자) 페이지 API. ML API 상태는 실제로 확인하고, 나머지는 가짜 데이터.
// 실제로는 Spring 이 관리자 권한(role=admin)을 확인한 뒤에만 응답해야 한다.
import { fake } from "./client";
import { recalc } from "./auction";
import { pingMl } from "./ml";
import { notify, notifyAll } from "./notify";
import { BUILD, getNewsCollection, newsHealth } from "./collection";
import { DATA_SOURCES, INITIAL_NOTICES, INITIAL_REPORTS, MODEL_PERFORMANCE } from "../mocks/admin";
import { auctionsDb, usersDb } from "../mocks/auctions";
import { load, save } from "../mocks/store";
import { dateTime } from "../utils/format";

// ── 신고·분쟁 ──
export const getReports = () => fake(load("reports", INITIAL_REPORTS));

const RESULT_TEXT = { 처리완료: "조치를 완료했어요", 반려: "확인 결과 문제가 없어 종료했어요", 검토중: "검토를 시작했어요" };

/**
 * 신고 처리. notifyReporter 면 신고한 회원에게 처리 결과(메모 포함)를 알림으로 보낸다.
 * @param {number} id
 * @param {{status: string, memo: string, notifyReporter?: boolean}} patch
 */
export function processReport(id, { status, memo, notifyReporter = true }) {
  const rows = load("reports", INITIAL_REPORTS).map((r) => (r.id === id ? { ...r, status, memo, processed_at: new Date().toISOString() } : r));
  save("reports", rows);
  const r = rows.find((x) => x.id === id);
  if (notifyReporter && RESULT_TEXT[status])
    notify(r.reporter, {
      type: "report",
      title: `신고 ${status === "검토중" ? "검토 시작" : "처리 결과"}`,
      body: `'${r.type}' 신고(${r.target}): ${RESULT_TEXT[status]}.${memo.trim() ? ` ${memo.trim()}` : ""}`,
      link: "/mypage?tab=reports",
    });
  return fake(r);
}

// ── 비정상 입찰 취소 ──

/**
 * 선택한 입찰을 취소하고 현재가를 다시 계산한다. 기록은 지우지 않고 "취소됨"으로 남긴다.
 * 취소된 입찰자와 판매자에게 알림을 보낸다.
 * @param {number} auctionId
 * @param {number[]} bidIndexes  경매의 bids 배열 위치
 */
export function cancelBids(auctionId, bidIndexes, reason) {
  if (!bidIndexes.length) return Promise.reject(new Error("취소할 입찰을 고르세요"));
  if (!reason.trim()) return Promise.reject(new Error("취소 사유를 적어주세요"));
  const rows = auctionsDb.all();
  const a = rows.find((x) => x.id === auctionId);
  const now = new Date().toISOString();
  const cancelledUsers = [];
  bidIndexes.forEach((i) => {
    const b = a.bids[i];
    if (b && !b.cancelled) {
      Object.assign(b, { cancelled: true, cancelled_at: now, cancel_reason: reason.trim() });
      cancelledUsers.push(b.user);
    }
  });
  recalc(a);
  auctionsDb.saveAll(rows);
  const link = `/auctions/${a.id}`;
  notify(cancelledUsers, { type: "auction", title: "입찰 취소", body: `'${a.title}'의 입찰이 관리자에 의해 취소되었어요. 사유: ${reason.trim()}`, link });
  notify(a.seller, { type: "auction", title: "비정상 입찰 정리", body: `'${a.title}'의 비정상 입찰 ${cancelledUsers.length}건이 취소되어 현재가가 ${a.current_bid.toLocaleString()}원으로 조정되었어요.`, link });
  return fake(a);
}

// ── 공지사항 (홈 배너에도 사용) ──
const sortNotices = (rows) =>
  [...rows].sort((a, b) => Number(b.pinned) - Number(a.pinned) || new Date(b.created_at) - new Date(a.created_at));

export const getNotices = () => fake(sortNotices(load("notices", INITIAL_NOTICES)), 150);

/** sendNotification 이면 새 공지를 모든 회원에게 알림으로도 보낸다 */
export function saveNotice({ sendNotification, ...notice }) {
  const rows = load("notices", INITIAL_NOTICES);
  if (sendNotification) notifyAll({ type: "notice", title: `공지 · ${notice.category}`, body: notice.title, link: "/" });
  if (notice.id) {
    const i = rows.findIndex((n) => n.id === notice.id);
    rows[i] = { ...rows[i], ...notice };
  } else {
    rows.push({ ...notice, id: Math.max(0, ...rows.map((n) => n.id)) + 1, created_at: new Date().toISOString() });
  }
  save("notices", rows);
  return fake(sortNotices(rows));
}

export function deleteNotice(id) {
  const rows = load("notices", INITIAL_NOTICES).filter((n) => n.id !== id);
  save("notices", rows);
  return fake(sortNotices(rows));
}

// ── 서버·API 상태 ──
export async function getSystemStatus() {
  const [ml, news] = await Promise.all([pingMl(), getNewsCollection().catch((e) => ({ error: e.message }))]);
  const health = news.log && !news.sample ? newsHealth(news.log) : null;
  return [
    { name: "웹 화면 (배포 버전)", ok: true, ms: null, detail: buildText() },
    {
      name: "뉴스 수집기",
      ok: health?.level === "ok",
      warn: health?.level === "warn",
      pending: !health && !news.error,
      ms: null,
      detail: health ? `${health.label} · ${health.detail}` : news.error ?? "서버에 연결하지 않음 (VITE_NEWS_URL)",
    },
    { name: "ML API (FastAPI)", ok: ml.ok, ms: ml.ms, detail: ml.ok ? `model ${ml.detail.model_version}` : ml.detail },
    { name: "Backend (Spring Boot)", ok: false, ms: null, detail: "아직 개발 전 — 가짜 데이터 사용 중", pending: true },
    { name: "Database (PostgreSQL)", ok: false, ms: null, detail: "Spring 연결 후 확인 가능", pending: true },
  ];
}

/** 배포 버전 한 줄: "abc1234 · Merge pull request #7 … · 커밋 10/22 15:37 · 빌드 10/22 15:45" */
export function buildText() {
  if (BUILD.dev) return "개발 중 (npm run dev)";
  if (!BUILD.sha) return `버전 정보 없음 · 빌드 ${BUILD.builtAt ? dateTime(BUILD.builtAt) : "-"}`;
  return [BUILD.sha, BUILD.message, BUILD.committedAt && `커밋 ${dateTime(BUILD.committedAt)}`, BUILD.builtAt && `빌드 ${dateTime(BUILD.builtAt)}`].filter(Boolean).join(" · ");
}

// ── 데이터 수집 현황 ──

/**
 * 데이터 원천 목록 + 뉴스 수집 현황. 뉴스 줄은 서버 수집 기록으로 채운다 (서버에 못 가면 news.error)
 * @returns {Promise<{rows: object[], news: object}>}
 */
export async function getCollectionStatus() {
  const news = await getNewsCollection().catch((e) => ({ error: e.message }));
  const health = news.log ? newsHealth(news.log) : null;
  const latest = news.log?.runs?.find((r) => r.ok);
  const rows = DATA_SOURCES.map((s) =>
    s.key !== "news"
      ? s
      : {
          ...s,
          last_run: news.log?.runs?.[0]?.finished_at ?? null,
          ranges: latest?.oldest_at ? [[latest.oldest_at.slice(0, 10), null]] : undefined,
          rangeText: latest ? `기사 ${latest.stored_total ?? "?"}건` : news.error ? "서버 연결 안 됨" : "-",
          health,
        },
  );
  return { rows, news };
}

// ── 모델 성능 ──
export const getModelPerformance = () => fake(MODEL_PERFORMANCE);

// ── 회원·경매 관리 ──
export const getUsers = () => fake(usersDb.all().map(({ password, ...u }) => u));

export function setUserStatus(id, status) {
  const rows = usersDb.all().map((u) => (u.id === id ? { ...u, status } : u));
  usersDb.saveAll(rows);
  return getUsers();
}

export const getAllAuctions = () => fake(auctionsDb.all().map(({ bids, ...a }) => a));

const AUCTION_STATUS_TEXT = { 진행중: "승인되어 경매 마켓에 올라갔어요", 중단: "관리자에 의해 중단되었어요" };

export function setAuctionStatus(id, status) {
  const rows = auctionsDb.all().map((a) => (a.id === id ? { ...a, status } : a));
  auctionsDb.saveAll(rows);
  const a = rows.find((x) => x.id === id);
  if (AUCTION_STATUS_TEXT[status])
    notify(a.seller, { type: "auction", title: `경매 ${status === "진행중" ? "승인" : "중단"}`, body: `'${a.title}' 경매가 ${AUCTION_STATUS_TEXT[status]}.`, link: `/auctions/${a.id}` });
  return getAllAuctions();
}
