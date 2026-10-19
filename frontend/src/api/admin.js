// 개발자(관리자) 페이지 API. ML API 상태는 실제로 확인하고, 나머지는 가짜 데이터.
// 실제로는 Spring 이 관리자 권한(role=admin)을 확인한 뒤에만 응답해야 한다.
import { fake } from "./client";
import { pingMl } from "./ml";
import { COLLECTION_STATUS, INITIAL_NOTICES, INITIAL_REPORTS, MODEL_PERFORMANCE } from "../mocks/admin";
import { auctionsDb, usersDb } from "../mocks/auctions";
import { load, save } from "../mocks/store";

// ── 신고·분쟁 ──
export const getReports = () => fake(load("reports", INITIAL_REPORTS));

export function updateReport(id, patch) {
  const rows = load("reports", INITIAL_REPORTS).map((r) => (r.id === id ? { ...r, ...patch } : r));
  save("reports", rows);
  return fake(rows.find((r) => r.id === id));
}

// ── 공지사항 (홈 배너에도 사용) ──
const sortNotices = (rows) =>
  [...rows].sort((a, b) => Number(b.pinned) - Number(a.pinned) || new Date(b.created_at) - new Date(a.created_at));

export const getNotices = () => fake(sortNotices(load("notices", INITIAL_NOTICES)), 150);

export function saveNotice(notice) {
  const rows = load("notices", INITIAL_NOTICES);
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
  const ml = await pingMl();
  return [
    { name: "ML API (FastAPI)", ok: ml.ok, ms: ml.ms, detail: ml.ok ? `model ${ml.detail.model_version}` : ml.detail },
    { name: "Backend (Spring Boot)", ok: false, ms: null, detail: "아직 개발 전 — 가짜 데이터 사용 중", pending: true },
    { name: "Database (PostgreSQL)", ok: false, ms: null, detail: "Spring 연결 후 확인 가능", pending: true },
  ];
}

// ── 데이터 수집 현황 ──
export const getCollectionStatus = () => fake(COLLECTION_STATUS);

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

export function setAuctionStatus(id, status) {
  const rows = auctionsDb.all().map((a) => (a.id === id ? { ...a, status } : a));
  auctionsDb.saveAll(rows);
  return getAllAuctions();
}
