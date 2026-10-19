// 게시판 (Spring 담당). 지금은 브라우저에 저장되는 가짜 데이터로 동작한다.
// 맨 위 공지는 관리자 공지사항(api/admin.js getNotices)을 그대로 보여준다.
import { fake } from "./client";
import { notify } from "./notify";
import { BOARD_CATEGORIES, postsDb } from "../mocks/board";
import { usersDb } from "../mocks/auctions";

export { BOARD_CATEGORIES };
export const PAGE_SIZE = 15;

const nameOf = (users, id) => users.find((u) => u.id === id)?.name ?? "알 수 없음";
const withAuthor = (users) => (p) => ({ ...p, author_name: nameOf(users, p.author) });
const newestFirst = (a, b) => b.id - a.id;

/**
 * 글 목록 (숨김 글 제외)
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
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const cur = Math.min(Math.max(1, page), pages);
  return fake({
    rows: rows.slice((cur - 1) * PAGE_SIZE, cur * PAGE_SIZE).map(({ body, ...p }) => withAuthor(users)(p)),
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
  if (!user) return Promise.reject(new Error("로그인 후 글을 쓸 수 있습니다"));
  const err = validate(form);
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
  const err = validate(form);
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
  return fake(true);
}

// ── 관리자: 게시판 관리 ──

/** 숨김 글 포함 전체 (관리자) */
export function getAllPosts() {
  const users = usersDb.all();
  return fake(postsDb.all().sort(newestFirst).map(withAuthor(users)));
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
  notify(p.author, { type: "notice", title: "게시글 삭제", body: `'${p.title}' 글이 관리자에 의해 삭제되었어요.${reason.trim() ? ` 사유: ${reason.trim()}` : ""}`, link: "/board" });
  return fake(true);
}
