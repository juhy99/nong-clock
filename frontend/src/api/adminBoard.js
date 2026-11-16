// 관리자 로그인 · 게시판 관리 (11-14) — Spring /api/admin/… (명세서 2-12). 관리자 계정은 DB 표 admin (일반 회원과 따로, SQL 로 넣음)
// 공지는 관리자가 게시판 관리에서 말머리 "공지"로 쓴 글 → 사용자 게시판 맨 위 (GET /api/notices)
import axios from "axios";

const api = axios.create({ timeout: 8000 });

/** 서버 응답 → 데이터, 오류 → 서버가 보낸 {"message"} 문장 + status */
const call = (req, fallback) =>
  req.then(
    (r) => r.data,
    (e) => {
      const err = new Error(e.response?.data?.message || (e.response ? fallback : "서버에 연결할 수 없습니다"));
      err.status = e.response?.status ?? 0;
      throw err;
    },
  );

// ── 관리자 로그인 ──
export const adminLogin = (email, password) => call(api.post("/api/admin/auth/login", { email: email.trim(), password }), "로그인하지 못했습니다");
export const adminLogout = () => api.post("/api/admin/auth/logout").catch(() => {});
/** 지금 관리자로 로그인돼 있으면 {id,email,name}, 아니면 null */
export const adminMe = () =>
  api.get("/api/admin/me").then(
    (r) => r.data,
    (e) => {
      if (e.response && [401, 403].includes(e.response.status)) return null;
      throw new Error(e.response ? "관리자 정보를 확인하지 못했습니다" : "서버에 연결할 수 없습니다");
    },
  );

// ── 게시판 관리 ──
export const ADMIN_CATEGORIES = ["공지", "자유", "질문", "정보", "거래후기"];

/** @param {{category?: string, q?: string, status?: ""|"VISIBLE"|"HIDDEN", page?: number}} opts */
export const adminPosts = ({ category = "", q = "", status = "", page = 1 } = {}) =>
  call(api.get("/api/admin/posts", { params: { category: category || undefined, q: q.trim() || undefined, status: status || undefined, page } }), "글 목록을 불러오지 못했습니다");
export const adminPost = (id) => call(api.get(`/api/admin/posts/${id}`), "글을 불러오지 못했습니다");
export const adminWritePost = (form) => call(api.post("/api/admin/posts", form), "글을 올리지 못했습니다");
export const adminUpdatePost = (id, form) => call(api.put(`/api/admin/posts/${id}`, form), "글을 고치지 못했습니다");
export const adminHidePost = (id, hidden, reason = "") => call(api.patch(`/api/admin/posts/${id}`, { hidden, reason }), "숨기기를 바꾸지 못했습니다");
export const adminDeletePost = (id) => call(api.delete(`/api/admin/posts/${id}`), "글을 지우지 못했습니다");
export const adminComments = (postId) => call(api.get(`/api/admin/posts/${postId}/comments`), "댓글을 불러오지 못했습니다");
export const adminWriteComment = (postId, body, parent_id = null) => call(api.post(`/api/admin/posts/${postId}/comments`, { body, parent_id }), "댓글을 올리지 못했습니다");
export const adminDeleteComment = (id) => call(api.delete(`/api/admin/comments/${id}`), "댓글을 지우지 못했습니다");

/** 사용자 게시판 맨 위 공지 (누구나) */
export const getNotices = () => call(api.get("/api/notices"), "공지를 불러오지 못했습니다");
