import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { activeBan, banText, createComment, deleteComment, getComments } from "../../api/board";
import { useAuth } from "../../components/AuthContext";
import { useAsync } from "../../components/common";
import ReportModal from "../../components/ReportModal";
import { boardDate } from "../../utils/format";

function CommentForm({ onSubmit, placeholder, autoFocus, onCancel }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSubmit(body);
      setBody("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="comment-form" onSubmit={submit}>
      <textarea className="input" rows={2} maxLength={500} placeholder={placeholder} value={body} onChange={(e) => setBody(e.target.value)} autoFocus={autoFocus} aria-label={placeholder} />
      <div className="comment-form-foot">
        <span className={`hint ${error ? "error" : ""}`}>{error || `${body.length}/500`}</span>
        <span style={{ display: "flex", gap: 6 }}>
          {onCancel && <button type="button" className="btn sm" onClick={onCancel}>취소</button>}
          <button className="btn sm primary" disabled={busy || !body.trim()}>등록</button>
        </span>
      </div>
    </form>
  );
}

function Comment({ c, post, reply, actions }) {
  return (
    <div id={`c${c.id}`} className={`comment ${reply ? "reply" : ""} ${c.deleted ? "deleted" : ""}`}>
      {reply && <span className="reply-mark" aria-hidden>↳</span>}
      <div style={{ flex: 1, minWidth: 0 }}>
        {c.deleted ? (
          <p className="muted small" style={{ margin: 0 }}>삭제된 댓글입니다.</p>
        ) : (
          <>
            <div className="comment-head">
              <b>{c.author_name}</b>
              {c.author === post.author && <span className="badge green">글쓴이</span>}
              <span className="muted small">{boardDate(c.created_at)}</span>
            </div>
            <p className="comment-body">{c.body}</p>
            <div className="comment-actions">{actions}</div>
          </>
        )}
      </div>
    </div>
  );
}

/** 글 아래 댓글·답글 (답글은 1단계까지, 답글에 답하면 같은 댓글 아래에 붙는다) */
export default function Comments({ post }) {
  const { user } = useAuth();
  const loc = useLocation();
  const state = useAsync(() => getComments(post.id), [post.id]);
  const [replyTo, setReplyTo] = useState(null);
  const [reporting, setReporting] = useState(null);
  const ban = user ? activeBan(user.id) : null;

  // 알림에서 들어오면 (#c12) 그 댓글로 스크롤
  useEffect(() => {
    if (state.data && loc.hash) document.querySelector(loc.hash)?.scrollIntoView({ block: "center" });
  }, [state.data, loc.hash]);

  const add = async (body, parent_id) => {
    await createComment(user, post.id, { body, parent_id });
    setReplyTo(null);
    state.reload();
  };
  const remove = async (c) => {
    if (!confirm("댓글을 지울까요?")) return;
    await deleteComment(user, c.id);
    state.reload();
  };
  const actions = (c) =>
    user && (
      <>
        {!ban && <button className="link small" onClick={() => setReplyTo(replyTo === c.id ? null : c.id)}>답글</button>}
        {c.author === user.id ? (
          <button className="link small muted" onClick={() => remove(c)}>삭제</button>
        ) : (
          <button className="link small muted" onClick={() => setReporting(c)}>신고</button>
        )}
      </>
    );

  const rows = state.data ?? [];
  const count = rows.reduce((n, c) => n + (c.deleted ? 0 : 1) + c.replies.filter((r) => !r.deleted).length, 0);

  return (
    <section className="card comments">
      <h3>댓글 <span className="count">{count}</span></h3>
      {state.loading && !state.data && <div className="state">불러오는 중…</div>}
      {state.error && <div className="state error">{state.error.message}</div>}
      {state.data && rows.length === 0 && <p className="muted small">첫 댓글을 남겨 보세요.</p>}
      {rows.map((c) => (
        <div key={c.id} className="comment-thread">
          <Comment c={c} post={post} actions={actions(c)} />
          {c.replies.map((r) => (
            <Comment key={r.id} c={r} post={post} reply actions={actions(r)} />
          ))}
          {/* 답글 쓰기: 원댓글이나 그 답글 어디서 눌러도 이 댓글 아래에 붙는다 */}
          {[c, ...c.replies].some((x) => x.id === replyTo) && (
            <div className="comment reply">
              <span className="reply-mark" aria-hidden>↳</span>
              <div style={{ flex: 1 }}>
                <CommentForm
                  autoFocus
                  placeholder={`${[c, ...c.replies].find((x) => x.id === replyTo).author_name}님에게 답글`}
                  onSubmit={(body) => add(body, replyTo)}
                  onCancel={() => setReplyTo(null)}
                />
              </div>
            </div>
          )}
        </div>
      ))}
      {!user ? (
        <p className="muted small comment-login">
          댓글을 쓰려면 <Link className="link" to={`/login?next=/board/${post.id}`}>로그인</Link>하세요.
        </p>
      ) : ban ? (
        <div className="banner small">⛔ 게시판 이용이 제한되어 댓글을 쓸 수 없어요 ({banText(ban)} · 사유: {ban.reason})</div>
      ) : (
        <CommentForm placeholder="댓글을 남겨 보세요" onSubmit={(body) => add(body, null)} />
      )}
      {reporting && (
        <ReportModal
          target={{ kind: "comment", id: reporting.id, label: `${reporting.author_name}: ${reporting.body.slice(0, 30)}`, post_id: post.id }}
          onClose={() => setReporting(null)}
        />
      )}
    </section>
  );
}
