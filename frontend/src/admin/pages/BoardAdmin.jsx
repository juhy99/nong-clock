import { Fragment, useState } from "react";
import {
  ADMIN_CATEGORIES,
  ADMIN_FILTER_CATEGORIES,
  adminComments,
  adminDeleteComment,
  adminDeletePost,
  adminHidePost,
  adminPost,
  adminPosts,
  adminUpdatePost,
  adminWriteComment,
  adminWritePost,
} from "../../api/adminBoard";
import { Async, SectionHead, useAsync } from "../../components/common";
import { getFlood } from "../../api/adminOps";
import { dateTime } from "../../utils/format";
import { SITE_URL } from "../siteUrl";

/**
 * 게시판 관리 · 공지 (11-14, 실제 DB — Spring /api/admin/posts…)
 * - 회원 글: 내용 확인, 숨기기(사유)·다시 보이기, 삭제, 관리자 댓글·답글, 댓글 삭제
 * - 관리자 글: 말머리 "공지"로 쓰면 사용자 게시판 맨 위에 보임. 관리자 글만 고칠 수 있음
 * 관리자는 사용자 사이트 회원이 아니라 사용자 사이트에서는 글·댓글을 쓰지 않는다 — 여기서만
 */

/** 글쓰기·고치기 칸 (관리자 글) */
function PostForm({ initial, onDone, onCancel }) {
  const [f, setF] = useState(initial ?? { category: "공지", title: "", body: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (initial?.id) await adminUpdatePost(initial.id, { category: f.category, title: f.title, body: f.body });
      else await adminWritePost({ category: f.category, title: f.title, body: f.body });
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <select className="input" style={{ maxWidth: 140 }} aria-label="말머리" value={f.category} onChange={set("category")}>
          {ADMIN_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <input className="input" style={{ flex: 1, minWidth: 200 }} aria-label="제목" placeholder="제목 (2~80자)" maxLength={80} value={f.title} onChange={set("title")} />
      </div>
      <textarea className="input" aria-label="내용" rows={6} placeholder="내용 (5자 이상)" value={f.body} onChange={set("body")} />
      {error && <span className="hint error">{error}</span>}
      <div style={{ display: "flex", gap: 8 }}>
        <button className="btn primary sm" disabled={busy}>{initial?.id ? "고치기" : "올리기"}</button>
        {onCancel && <button type="button" className="btn sm" onClick={onCancel}>취소</button>}
      </div>
    </form>
  );
}

/** 관리자 댓글·답글 쓰는 칸 */
function CommentForm({ postId, parentId, placeholder, onDone }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await adminWriteComment(postId, body, parentId);
      setBody("");
      onDone();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <form onSubmit={submit} style={{ display: "flex", gap: 6, alignItems: "flex-start", flexWrap: "wrap" }}>
      <textarea className="input" rows={2} style={{ flex: 1, minWidth: 200 }} maxLength={500} placeholder={placeholder} value={body} onChange={(e) => setBody(e.target.value)} />
      <button className="btn sm primary" disabled={!body.trim()}>등록</button>
      {error && <span className="hint error" style={{ width: "100%" }}>{error}</span>}
    </form>
  );
}

/** 글의 댓글·답글: 삭제, 관리자 답글, 관리자 댓글 */
function PostComments({ postId, onChange }) {
  const state = useAsync(() => adminComments(postId), [postId]);
  const [replyTo, setReplyTo] = useState(null);
  const [error, setError] = useState("");
  const reload = () => {
    setReplyTo(null);
    state.reload();
    onChange();
  };
  async function remove(c) {
    if (!confirm("이 댓글을 지울까요? (답글이 있으면 '삭제된 댓글' 자리만 남아요)")) return;
    setError("");
    try {
      await adminDeleteComment(c.id);
      reload();
    } catch (err) {
      setError(err.message);
    }
  }
  const one = (c, reply) => (
    <div key={c.id} className={`admin-comment ${reply ? "reply" : ""}`}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="small">
          {reply && "↳ "}
          <b>{c.author_name}</b> {c.by_admin && <span className="badge red">관리자</span>} <span className="muted">· {dateTime(c.created_at)}</span>
        </div>
        <div className={c.deleted ? "muted small" : ""} style={{ whiteSpace: "pre-wrap" }}>{c.deleted ? "삭제된 댓글 (답글이 있어 자리만 남음)" : c.body}</div>
        {replyTo === c.id && <CommentForm postId={postId} parentId={c.id} placeholder={`${c.author_name}님에게 관리자 답글`} onDone={reload} />}
      </div>
      {!c.deleted && (
        <span style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
          <button className="btn sm" onClick={() => setReplyTo(replyTo === c.id ? null : c.id)}>{replyTo === c.id ? "닫기" : "답글"}</button>
          <button className="btn sm danger" onClick={() => remove(c)}>삭제</button>
        </span>
      )}
    </div>
  );
  return (
    <div style={{ display: "grid", gap: 8 }}>
      <Async state={state} empty="댓글이 없습니다">
        {(rows) => <div className="admin-comments">{rows.map((c) => <Fragment key={c.id}>{one(c, false)}{(c.replies ?? []).map((r) => one(r, true))}</Fragment>)}</div>}
      </Async>
      {error && <span className="hint error">{error}</span>}
      <CommentForm postId={postId} placeholder="관리자 댓글 (사용자 화면에 '관리자'로 보여요)" onDone={reload} />
    </div>
  );
}

/** 펼친 글: 본문, 숨기기·삭제·고치기, 댓글 */
function PostDetail({ id, onChange }) {
  const state = useAsync(() => adminPost(id), [id]);
  const [reason, setReason] = useState("");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  async function run(fn) {
    setError("");
    try {
      await fn();
      setReason("");
      state.reload();
      onChange();
    } catch (err) {
      setError(err.message);
    }
  }
  return (
    <Async state={state}>
      {(p) => (
        <div style={{ display: "grid", gap: 10 }}>
          {editing ? (
            <PostForm initial={p} onCancel={() => setEditing(false)} onDone={() => { setEditing(false); state.reload(); onChange(); }} />
          ) : (
            <div style={{ whiteSpace: "pre-wrap" }}>{p.body}</div>
          )}
          {p.status === "HIDDEN" && <div className="small muted">숨김 사유: {p.hidden_reason}</div>}
          {p.status !== "HIDDEN" && (
            <input className="input" placeholder="숨기는 사유 (필수, 관리 기록용 — 사용자에게는 보이지 않음)" maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {p.status !== "HIDDEN" && <a className="btn sm" href={`${SITE_URL}/board/${p.id}`} target="_blank" rel="noreferrer">사이트에서 보기 ↗</a>}
            {p.by_admin && !editing && <button className="btn sm" onClick={() => setEditing(true)}>고치기</button>}
            {p.status === "HIDDEN" ? (
              <button className="btn sm" onClick={() => run(() => adminHidePost(p.id, false))}>다시 보이기</button>
            ) : (
              <button className="btn sm" onClick={() => run(() => adminHidePost(p.id, true, reason))}>숨기기</button>
            )}
            <button className="btn sm danger" onClick={() => confirm("이 글을 완전히 삭제할까요? (댓글도 같이 지워져요)") && run(() => adminDeletePost(p.id))}>삭제</button>
          </div>
          {error && <span className="hint error">{error}</span>}
          <div className="admin-sub">
            <b className="small">댓글 {p.comment_count}개</b>
            <PostComments postId={p.id} onChange={() => { state.reload(); onChange(); }} />
          </div>
        </div>
      )}
    </Async>
  );
}

/** 도배 감지 (11-17): 최근 1시간 · 24시간에 글+댓글을 많이 쓴 회원 (Spring /api/admin/ops/flood). 없으면 아무것도 안 보임 */
function FloodCard() {
  const state = useAsync(getFlood);
  const d = state.data;
  if (!d || !d.rows.length) return null;
  return (
    <div className="alert-band warn" role="alert">
      <b>⚠️ 짧은 시간에 많이 쓴 회원 {d.rows.length}명</b>
      <span>{d.rows.map((r) => `${r.nickname} (1시간 ${r.last_hour} · 하루 ${r.last_day})`).join(" · ")} — 기준: 1시간 {d.hour_limit}건 · 하루 {d.day_limit}건. 아래 검색창에 닉네임을 넣어 글을 확인하세요</span>
    </div>
  );
}

export default function BoardAdmin() {
  const [filter, setFilter] = useState({ category: "", q: "", status: "", page: 1 });
  const [keyword, setKeyword] = useState("");
  const [open, setOpen] = useState(null);
  const [writing, setWriting] = useState(false);
  const state = useAsync(() => adminPosts(filter), [filter.category, filter.q, filter.status, filter.page]);
  const go = (patch) => {
    setOpen(null);
    setFilter({ ...filter, page: 1, ...patch });
  };

  return (
    <>
      <FloodCard />
      <section className="card">
        <SectionHead
          title="공지 · 관리자 글쓰기"
          desc={'말머리 "공지"로 쓰면 사용자 게시판 맨 위에 보여요. 작성자는 "관리자"로 표시돼요'}
          right={!writing && <button className="btn primary sm" onClick={() => setWriting(true)}>✏️ 새 글</button>}
        />
        {writing && <PostForm onCancel={() => setWriting(false)} onDone={() => { setWriting(false); setOpen(null); state.reload(); }} />}
      </section>

      <section className="card">
        <SectionHead title="게시판 관리" desc="회원 글·공지 전체 (숨긴 글 포함). 숨긴 글은 사용자에게 보이지 않아요" />
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          <select className="input" style={{ maxWidth: 140 }} value={filter.category} onChange={(e) => go({ category: e.target.value })} aria-label="말머리">
            <option value="">전체 말머리</option>
            {ADMIN_FILTER_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select className="input" style={{ maxWidth: 140 }} value={filter.status} onChange={(e) => go({ status: e.target.value })} aria-label="상태">
            <option value="">전체 상태</option>
            <option value="VISIBLE">공개</option>
            <option value="HIDDEN">숨김</option>
          </select>
          <form style={{ display: "flex", gap: 6 }} onSubmit={(e) => { e.preventDefault(); go({ q: keyword.trim() }); }}>
            <input className="input" style={{ maxWidth: 240 }} placeholder="제목·내용·작성자 검색" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            <button className="btn sm">검색</button>
          </form>
        </div>
        <Async state={state} empty="글이 없습니다">
          {(d) => (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>#</th><th>말머리</th><th>제목</th><th>작성자</th><th>작성일</th><th className="r">조회</th><th>상태</th><th /></tr>
                  </thead>
                  <tbody>
                    {d.rows.length === 0 && <tr><td colSpan={8} className="state">조건에 맞는 글이 없습니다</td></tr>}
                    {d.rows.map((p) => (
                      <Fragment key={p.id}>
                        <tr className={p.status === "HIDDEN" ? "muted" : ""}>
                          <td className="muted small">{p.id}</td>
                          <td><span className={`badge ${p.category === "공지" ? "red" : ""}`}>{p.category}</span></td>
                          <td>{p.title}{p.comment_count > 0 && <span className="muted small"> [{p.comment_count}]</span>}</td>
                          <td className="small">{p.by_admin ? <span className="badge red">관리자</span> : p.author_name}</td>
                          <td className="small num">{dateTime(p.created_at)}</td>
                          <td className="r small num">{p.views}</td>
                          <td>{p.status === "HIDDEN" ? <span className="badge red" title={p.hidden_reason}>숨김</span> : <span className="badge green">공개</span>}</td>
                          <td className="r">
                            <button className="btn sm" onClick={() => setOpen(open === p.id ? null : p.id)}>{open === p.id ? "닫기" : "관리"}</button>
                          </td>
                        </tr>
                        {open === p.id && (
                          <tr>
                            <td colSpan={8} style={{ background: "#fafaf7" }}>
                              <PostDetail id={p.id} onChange={state.reload} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              {d.pages > 1 && (
                <nav className="pager" aria-label="페이지">
                  <button className="btn sm" disabled={d.page === 1} onClick={() => go({ page: d.page - 1 })}>이전</button>
                  <span className="small muted">{d.page} / {d.pages} 쪽 · 전체 {d.total}개</span>
                  <button className="btn sm" disabled={d.page === d.pages} onClick={() => go({ page: d.page + 1 })}>다음</button>
                </nav>
              )}
            </>
          )}
        </Async>
      </section>
    </>
  );
}
