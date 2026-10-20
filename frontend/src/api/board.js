// 게시판 (Spring 담당). 지금은 브라우저에 저장되는 가짜 데이터로 동작한다.
// 맨 위 공지는 관리자 공지사항(api/admin.js getNotices)을 그대로 보여준다.
import { fake } from "./client";
import { notify } from "./notify";
import { BOARD_CATEGORIES, commentsDb, postsDb } from "../mocks/board";
import { usersDb } from "../mocks/auctions";

export { BOARD_CATEGORIES };
export const PAGE_SIZE = 15;

const nameOf = (users, id) => users.find((u) => u.id === id)?.name ?? "알 수 없음";
const withAuthor = (users) => (p) => ({ ...p, author_name: nameOf(users, p.author) });
const newestFirst = (a, b) => b.id - a.id;
const commentCounts = () =>
  commentsDb.all().reduce((m, c) => (c.deleted ? m : { ...m, [c.post_id]: (m[c.post_id] ?? 0) + 1 }), {});

// ── 게시판 이용 제한 (관리자가 거는 글·댓글 작성 금지) ──

export const BAN_DAYS = [3, 7, 30, null]; // null = 영구

/** 지금 걸려 있는 게시판 이용 제한 (없으면 null) */
export function activeBan(userId) {
  const ban = usersDb.all().find((u) => u.id === userId)?.board_ban;
  if (!ban) return null;
  if (ban.until && new Date(ban.until) <= new Date()) return null;
  return ban;
}

export const banText = (ban) => (ban.until ? `${new Date(ban.until).toLocaleDateString("ko-KR")}까지` : "영구");

function checkCanWrite(user) {
  if (!user) return "로그인 후 쓸 수 있습니다";
  const ban = activeBan(user.id);
  if (ban) return `게시판 이용이 제한된 계정입니다 (${banText(ban)} · 사유: ${ban.reason})`;
  return null;
}

/** 검색 결과에 보여줄 본문 일부 (검색어 앞뒤) */
function snippetOf(body, keyword, len = 70) {
  const at = body.toLowerCase().indexOf(keyword);
  const start = at < 0 ? 0 : Math.max(0, at - 20);
  const text = body.slice(start, start + len);
  return `${start > 0 ? "…" : ""}${text}${start + len < body.length ? "…" : ""}`;
}

/**
 * 글 목록 (숨김 글 제외). 검색어가 있으면 본문 일부(snippet)도 함께
 * @param {{category?: string, q?: string, page?: number}} opts
 * @returns {Promise<{rows: object[], total: number, page: number, pages: number}>}
 */
export function getPosts({ category = "", q = "", page = 1 } = {}) {
  const users = usersDb.all();
  const keyword = q.trim().toLowerCase();
  const rows = postsDb
    .all()
    .filter((p) => !p.hidden && (!category || p.category === category))
    .filter((p) => !keyword || `${p.title} ${p.body} ${nameOf(users, p.author)}`.toLowerCase().includes(keyword))
    .sort(newestFirst);
  const counts = commentCounts();
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const cur = Math.min(Math.max(1, page), pages);
  return fake({
    rows: rows.slice((cur - 1) * PAGE_SIZE, cur * PAGE_SIZE).map(({ body, ...p }) => ({
      ...withAuthor(users)(p),
      comment_count: counts[p.id] ?? 0,
      ...(keyword && { snippet: snippetOf(body, keyword) }),
    })),
    total: rows.length,
    page: cur,
    pages,
  });
}

/** 글 보기. countView 면 조회수 +1 (같은 브라우저 탭에서는 한 번만) */
export function getPost(id, { countView = false } = {}) {
  const rows = postsDb.all();
  const p = rows.find((x) => x.id === Number(id));
  if (!p || p.hidden) return Promise.reject(new Error("삭제되었거나 볼 수 없는 글입니다"));
  const key = `farmbid-viewed:${p.id}`;
  if (countView && !sessionStorage.getItem(key)) {
    sessionStorage.setItem(key, "1");
    p.views += 1;
    postsDb.saveAll(rows);
  }
  return fake(withAuthor(usersDb.all())(p), 120);
}

function validate(form) {
  if (!BOARD_CATEGORIES.includes(form.category)) return "말머리를 고르세요";
  if (form.title.trim().length < 2) return "제목을 2자 이상 입력하세요";
  if (form.title.trim().length > 80) return "제목은 80자까지 쓸 수 있습니다";
  if (form.body.trim().length < 5) return "내용을 5자 이상 입력하세요";
  return null;
}

/** @param {{category: string, title: string, body: string, images: string[]}} form */
export function createPost(user, form) {
  const err = checkCanWrite(user) ?? validate(form);
  if (err) return Promise.reject(new Error(err));
  const rows = postsDb.all();
  const p = {
    id: Math.max(0, ...rows.map((x) => x.id)) + 1,
    category: form.category,
    title: form.title.trim(),
    body: form.body.trim(),
    images: form.images ?? [],
    author: user.id,
    created_at: new Date().toISOString(),
    updated_at: null,
    views: 0,
    hidden: false,
  };
  rows.push(p);
  postsDb.saveAll(rows);
  return fake(p);
}

export function updatePost(user, id, form) {
  const rows = postsDb.all();
  const p = rows.find((x) => x.id === Number(id));
  if (!p || p.author !== user?.id) return Promise.reject(new Error("본인 글만 고칠 수 있습니다"));
  const err = checkCanWrite(user) ?? validate(form);
  if (err) return Promise.reject(new Error(err));
  Object.assign(p, { category: form.category, title: form.title.trim(), body: form.body.trim(), images: form.images ?? [], updated_at: new Date().toISOString() });
  postsDb.saveAll(rows);
  return fake(p);
}

/** 작성자 본인 삭제 */
export function deletePost(user, id) {
  const rows = postsDb.all();
  const p = rows.find((x) => x.id === Number(id));
  if (!p || p.author !== user?.id) return Promise.reject(new Error("본인 글만 지울 수 있습니다"));
  postsDb.saveAll(rows.filter((x) => x.id !== p.id));
  commentsDb.saveAll(commentsDb.all().filter((c) => c.post_id !== p.id));
  return fake(true);
}

// ── 관리자: 게시판 관리 ──

/** 숨김 글 포함 전체 (관리자) */
export function getAllPosts() {
  const users = usersDb.all();
  const counts = commentCounts();
  return fake(postsDb.all().sort(newestFirst).map((p) => ({ ...withAuthor(users)(p), comment_count: counts[p.id] ?? 0, author_ban: activeBan(p.author) })));
}

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

/** 관리자 삭제 (작성자에게 알림) */
export function adminDeletePost(id, reason = "") {
  const rows = postsDb.all();
  const p = rows.find((x) => x.id === id);
  postsDb.saveAll(rows.filter((x) => x.id !== id));
  commentsDb.saveAll(commentsDb.all().filter((c) => c.post_id !== id));
  notify(p.author, { type: "notice", title: "게시글 삭제", body: `'${p.title}' 글이 관리자에 의해 삭제되었어요.${reason.trim() ? ` 사유: ${reason.trim()}` : ""}`, link: "/board" });
  return fake(true);
}

// ── 댓글·답글 ──

/**
 * 글의 댓글을 [{...댓글, replies: [...답글]}] 모양으로. 지운 댓글은 답글이 남아 있을 때만 "삭제된 댓글"로 남는다.
 */
export function getComments(postId) {
  const users = usersDb.all();
  const rows = commentsDb.all().filter((c) => c.post_id === Number(postId)).sort((a, b) => a.id - b.id).map(withAuthor(users));
  const top = rows.filter((c) => !c.parent_id).map((c) => ({ ...c, replies: rows.filter((r) => r.parent_id === c.id) }));
  return fake(top, 80);
}

/**
 * 댓글 쓰기. parent_id 가 있으면 답글. 글쓴이(내 글에 댓글)와 원댓글 작성자(내 댓글에 답글)에게 알림.
 * @param {{body: string, parent_id?: number}} form
 */
export function createComment(user, postId, { body, parent_id = null }) {
  const err = checkCanWrite(user);
  if (err) return Promise.reject(new Error(err));
  const text = body.trim();
  if (!text) return Promise.reject(new Error("댓글 내용을 입력하세요"));
  if (text.length > 500) return Promise.reject(new Error("댓글은 500자까지 쓸 수 있습니다"));
  const post = postsDb.all().find((p) => p.id === Number(postId));
  if (!post || post.hidden) return Promise.reject(new Error("댓글을 달 수 없는 글입니다"));
  const rows = commentsDb.all();
  let parent = parent_id ? rows.find((c) => c.id === parent_id && c.post_id === post.id) : null;
  if (parent_id && (!parent || parent.deleted)) return Promise.reject(new Error("삭제된 댓글에는 답글을 달 수 없습니다"));
  if (parent?.parent_id) parent = rows.find((c) => c.id === parent.parent_id); // 답글의 답글은 같은 댓글 아래로
  const c = { id: Math.max(0, ...rows.map((x) => x.id)) + 1, post_id: post.id, parent_id: parent?.id ?? null, author: user.id, body: text, created_at: new Date().toISOString(), deleted: false };
  rows.push(c);
  commentsDb.saveAll(rows);

  const link = `/board/${post.id}#c${c.id}`;
  const short = text.length > 40 ? `${text.slice(0, 40)}…` : text;
  const replyTo = parent_id ? rows.find((x) => x.id === parent_id)?.author : null; // 실제로 답한 댓글의 작성자
  if (replyTo && replyTo !== user.id) notify(replyTo, { type: "comment", title: "내 댓글에 답글", body: `${user.name}: ${short}`, link });
  if (post.author !== user.id && post.author !== replyTo) notify(post.author, { type: "comment", title: "내 글에 댓글", body: `'${post.title}' — ${user.name}: ${short}`, link });
  return fake(c);
}

/**
 * 댓글 삭제 (작성자 본인 또는 관리자). 답글이 달린 댓글은 내용만 지우고 "삭제된 댓글입니다"로 남긴다.
 * 관리자가 지우면 작성자에게 사유를 알린다.
 */
export function deleteComment(user, id, reason = "") {
  let rows = commentsDb.all();
  const c = rows.find((x) => x.id === id);
  const isAdmin = user?.type === "admin";
  if (!c || (c.author !== user?.id && !isAdmin)) return Promise.reject(new Error("본인 댓글만 지울 수 있습니다"));
  const liveReplies = rows.filter((r) => r.parent_id === c.id && !r.deleted).length;
  if (liveReplies) Object.assign(c, { deleted: true, body: "" });
  else rows = rows.filter((x) => x.id !== c.id);
  // 지운 원댓글에 답글이 하나도 안 남았으면 원댓글 자리도 정리
  const parent = c.parent_id && rows.find((x) => x.id === c.parent_id);
  if (parent?.deleted && !rows.some((r) => r.parent_id === parent.id && !r.deleted)) rows = rows.filter((x) => x.id !== parent.id && x.parent_id !== parent.id);
  commentsDb.saveAll(rows);
  if (isAdmin && c.author !== user.id)
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

/** 이용 제한 중인 회원 목록 */
export const getBannedUsers = () =>
  fake(usersDb.all().filter((u) => activeBan(u.id)).map((u) => ({ id: u.id, name: u.name, email: u.email, ban: u.board_ban })));

/** 관리자: 글의 모든 댓글 (평평한 목록) */
export const getPostComments = (postId) => {
  const users = usersDb.all();
  return fake(commentsDb.all().filter((c) => c.post_id === postId).sort((a, b) => a.id - b.id).map((c) => ({ ...withAuthor(users)(c), author_ban: activeBan(c.author) })));
};

/** 관리자: 숨김 글도 볼 수 있는 글 조회 (신고 처리 화면용) */
export function getPostForAdmin(id) {
  const p = postsDb.all().find((x) => x.id === Number(id));
  return p ? fake(withAuthor(usersDb.all())(p), 60) : Promise.reject(new Error("삭제된 글입니다"));
}
