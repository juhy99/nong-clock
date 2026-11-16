// 게시판 (Spring 담당). 맨 위 공지는 관리자가 게시판 관리에서 쓴 "공지" 글 (api/adminBoard.js getNotices, 11-14).
// 글·댓글은 언제나 Spring 서버(/api/posts…, /api/comments…, 명세서 2-9·2-10)로 (11-14: 가짜 게시판 없앰 — 서버가 안 되면 오류 안내).
//   작성자는 서버가 로그인 세션으로 정한다. 관리자 글(공지)·댓글은 "관리자"(by_admin)로 오고, 숨기기·삭제는 관리자 사이트(api/adminBoard.js)에서.
// 아래 "신고 처리·이용 제한" 부분은 숨긴 메뉴용 예시 데이터 (서버 API 없음). 실제 게시판 관리는 api/adminBoard.js
import axios from "axios";
import { fake } from "./client";
import { notify } from "./notify";
import { BOARD_CATEGORIES, commentsDb, postsDb } from "../mocks/board";
import { usersDb } from "../mocks/auctions";

export { BOARD_CATEGORIES };
export const PAGE_SIZE = 15;

const nameOf = (users, id) => users.find((u) => u.id === id)?.name ?? "알 수 없음";
const withAuthor = (users) => (p) => ({ ...p, author_name: nameOf(users, p.author) });

// ── 게시판 이용 제한 ──

export const BAN_DAYS = [3, 7, 30, null]; // null = 영구

/** 사용자 사이트: 지금 걸려 있는 게시판 이용 제한 — 서버에 이용 제한 기능이 아직 없어 늘 null */
export const activeBan = () => null;

/** 관리자 사이트(가짜 데이터)의 이용 제한 */
export function adminBanOf(userId) {
  const ban = usersDb.all().find((u) => u.id === userId)?.board_ban;
  if (!ban) return null;
  if (ban.until && new Date(ban.until) <= new Date()) return null;
  return ban;
}

// ── Spring 연결 ──
const api = axios.create({ timeout: 8000 });
/** 서버 응답 → 데이터, 오류 → 서버가 보낸 {"message"} 문장 */
const call = (req, fallback) =>
  req.then(
    (r) => r.data,
    (e) => {
      const err = new Error(e.response?.data?.message || (e.response ? fallback : "게시판 서버에 연결할 수 없습니다"));
      err.status = e.response?.status ?? 0; // 오류 팝업이 이 코드로 설명을 고름 (0 = 서버에 못 닿음)
      throw err;
    },
  );
const noPhotos = (form) => (form.images?.length ? Promise.reject(new Error("사진 첨부는 아직 준비 중이에요 (사진을 빼고 올려 주세요)")) : null);

export const banText = (ban) => (ban.until ? `${new Date(ban.until).toLocaleDateString("ko-KR")}까지` : "영구");

/**
 * 글 목록 (숨김 글 제외). 검색어가 있으면 본문 일부(snippet)도 함께
 * @param {{category?: string, q?: string, page?: number}} opts
 * @returns {Promise<{rows: object[], total: number, page: number, pages: number}>}
 */
export function getPosts({ category = "", q = "", page = 1 } = {}) {
  return call(api.get("/api/posts", { params: { category: category || undefined, q: q.trim() || undefined, page } }), "글 목록을 불러오지 못했습니다");
}

/**
 * 마이페이지 "내가 쓴 글 · 내가 쓴 댓글" (11-11).
 * Spring 에는 아직 API 가 없어(명세서 2-9 제안: GET /api/posts?mine=true, GET /api/me/comments) null 을 돌려주고 화면은 "준비 중"으로 보여 준다.
 * @returns {Promise<{posts: object[] | null, comments: object[] | null}>}
 */
export async function getMyActivity() {
  // 11-16: 마이페이지 '내가 쓴 글·댓글' = GET /api/me/posts · /api/me/comments (최근 100개). 못 불러오면 null → 화면이 안내
  const [posts, comments] = await Promise.all([
    call(api.get("/api/me/posts"), "내 글을 불러오지 못했습니다").catch(() => null),
    call(api.get("/api/me/comments"), "내 댓글을 불러오지 못했습니다").catch(() => null),
  ]);
  return { posts, comments };
}

/** 글 보기. countView 면 조회수 +1 (같은 브라우저 탭에서는 한 번만) */
export function getPost(id, { countView = false } = {}) {
  return call(api.get(`/api/posts/${id}`, { params: countView ? { view: true } : {} }), "글을 불러오지 못했습니다"); // 조회수 중복은 서버가 막음
}

/** @param {{category: string, title: string, body: string, images: string[]}} form */
export function createPost(user, form) {
  return noPhotos(form) ?? call(api.post("/api/posts", { category: form.category, title: form.title, body: form.body }), "글을 올리지 못했습니다");
}

export function updatePost(user, id, form) {
  return noPhotos(form) ?? call(api.put(`/api/posts/${id}`, { category: form.category, title: form.title, body: form.body }), "글을 고치지 못했습니다");
}

/** 작성자 본인 또는 관리자 삭제 (서버가 확인) */
export function deletePost(user, id) {
  return call(api.delete(`/api/posts/${id}`), "글을 지우지 못했습니다");
}

// ── 관리자 사이트 "신고 처리"(숨긴 메뉴)용 예시 데이터 — 실제 게시판 관리는 api/adminBoard.js (11-14) ──

/** 글 숨기기/다시 보이기. 숨길 때는 사유를 작성자에게 알림으로 보낸다. */
export function setPostHidden(id, hidden, reason = "") {
  const rows = postsDb.all();
  const p = rows.find((x) => x.id === id);
  if (hidden && !reason.trim()) return Promise.reject(new Error("숨기는 사유를 적어주세요"));
  Object.assign(p, { hidden, hidden_reason: hidden ? reason.trim() : "" });
  postsDb.saveAll(rows);
  if (hidden) notify(p.author, { type: "notice", title: "게시글 숨김", body: `'${p.title}' 글이 운영 정책에 따라 숨김 처리되었어요. 사유: ${reason.trim()}`, link: "/board" });
  return fake(p);
}

// ── 댓글·답글 ──

/**
 * 글의 댓글을 [{...댓글, replies: [...답글]}] 모양으로. 지운 댓글은 답글이 남아 있을 때만 "삭제된 댓글"로 남는다.
 */
export function getComments(postId) {
  return call(api.get(`/api/posts/${postId}/comments`), "댓글을 불러오지 못했습니다");
}

/**
 * 댓글 쓰기. parent_id 가 있으면 답글
 * @param {{body: string, parent_id?: number}} form
 */
export function createComment(user, postId, { body, parent_id = null }) {
  return call(api.post(`/api/posts/${postId}/comments`, { body, parent_id }), "댓글을 올리지 못했습니다");
}

/** 댓글 삭제 (작성자 본인 또는 관리자, 서버가 확인). 답글이 달린 댓글은 서버가 "삭제된 댓글"로 남긴다 */
export function deleteComment(user, id) {
  return call(api.delete(`/api/comments/${id}`), "댓글을 지우지 못했습니다");
}

/**
 * 관리자 사이트(가짜 데이터) 댓글 삭제. 답글이 달린 댓글은 내용만 지우고 "삭제된 댓글입니다"로 남긴다. 작성자에게 사유를 알린다.
 * 사용자 사이트의 실제 댓글은 deleteComment (서버) — 이 함수로 서버 댓글을 지우지 않음
 */
export function adminDeleteComment(user, id, reason = "") {
  let rows = commentsDb.all();
  const c = rows.find((x) => x.id === id);
  if (!c) return Promise.reject(new Error("이미 지워진 댓글입니다"));
  const liveReplies = rows.filter((r) => r.parent_id === c.id && !r.deleted).length;
  if (liveReplies) Object.assign(c, { deleted: true, body: "" });
  else rows = rows.filter((x) => x.id !== c.id);
  const parent = c.parent_id && rows.find((x) => x.id === c.parent_id);
  if (parent?.deleted && !rows.some((r) => r.parent_id === parent.id && !r.deleted)) rows = rows.filter((x) => x.id !== parent.id && x.parent_id !== parent.id);
  commentsDb.saveAll(rows);
  if (c.author !== user?.id)
    notify(c.author, { type: "notice", title: "댓글 삭제", body: `작성하신 댓글이 관리자에 의해 삭제되었어요.${reason.trim() ? ` 사유: ${reason.trim()}` : ""}`, link: `/board/${c.post_id}` });
  return fake(true);
}

// ── 관리자: 이용 제한 ──

/**
 * 게시판 이용 제한 걸기. days 가 null 이면 영구. 제한 중에는 글·댓글을 쓸 수 없다 (로그인·입찰은 가능).
 */
export function banUser(userId, days, reason) {
  if (!reason.trim()) return Promise.reject(new Error("제한 사유를 적어주세요"));
  const rows = usersDb.all();
  const u = rows.find((x) => x.id === userId);
  if (!u || u.type === "admin") return Promise.reject(new Error("제한할 수 없는 계정입니다"));
  u.board_ban = { until: days ? new Date(Date.now() + days * 86400000).toISOString() : null, reason: reason.trim(), at: new Date().toISOString() };
  usersDb.saveAll(rows);
  notify(userId, { type: "notice", title: "게시판 이용 제한", body: `${days ? `${days}일 동안` : "영구히"} 게시판 글·댓글을 쓸 수 없어요. 사유: ${reason.trim()}`, link: "/board" });
  return fake(u.board_ban);
}

export function liftBan(userId) {
  const rows = usersDb.all();
  const u = rows.find((x) => x.id === userId);
  delete u.board_ban;
  usersDb.saveAll(rows);
  notify(userId, { type: "notice", title: "게시판 이용 제한 해제", body: "다시 게시판에 글과 댓글을 쓸 수 있어요.", link: "/board" });
  return fake(true);
}

/** 관리자: 글의 모든 댓글 (평평한 목록) */
export const getPostComments = (postId) => {
  const users = usersDb.all();
  return fake(commentsDb.all().filter((c) => c.post_id === postId).sort((a, b) => a.id - b.id).map((c) => ({ ...withAuthor(users)(c), author_ban: adminBanOf(c.author) })));
};

/** 관리자: 숨김 글도 볼 수 있는 글 조회 (신고 처리 화면용) */
export function getPostForAdmin(id) {
  const p = postsDb.all().find((x) => x.id === Number(id));
  return p ? fake(withAuthor(usersDb.all())(p), 60) : Promise.reject(new Error("삭제된 글입니다"));
}
