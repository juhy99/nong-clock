import { Fragment, useState } from "react";
import { BOARD_CATEGORIES, adminDeletePost, banText, deleteComment, getAllPosts, getBannedUsers, getPostComments, liftBan, setPostHidden } from "../../api/board";
import { useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";
import Photo from "../../components/Photo";
import { dateTime } from "../../utils/format";
import { SITE_URL } from "../siteUrl";
import BanPanel from "./BanPanel";

/** 이용 제한 중인 회원 */
function BannedUsers({ version, onChange }) {
  const state = useAsync(getBannedUsers, [version]);
  return (
    <section className="card">
      <SectionHead title="게시판 이용 제한 중인 회원" desc="제한 중에는 글·댓글을 쓸 수 없어요 (로그인·입찰은 가능). 회원 전체 이용 정지는 '회원 관리'에서" />
      <Async state={state} empty="제한 중인 회원이 없습니다">
        {(rows) => (
          <table className="table">
            <tbody>
              {rows.map((u) => (
                <tr key={u.id}>
                  <td><b>{u.name}</b> <span className="muted small">{u.email}</span></td>
                  <td className="small">{banText(u.ban)}</td>
                  <td className="small">{u.ban.reason}</td>
                  <td className="r"><button className="btn sm" onClick={async () => { await liftBan(u.id); onChange(); }}>제한 풀기</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Async>
    </section>
  );
}

/** 글의 댓글: 삭제, 댓글 작성자 이용 제한 */
function PostComments({ postId, onChange }) {
  const { user } = useAuth();
  const state = useAsync(() => getPostComments(postId), [postId]);
  const [banFor, setBanFor] = useState(null);
  async function remove(c) {
    const reason = prompt("댓글을 지우는 사유 (작성자에게 전달됩니다)", "운영 정책 위반");
    if (reason === null) return;
    await deleteComment(user, c.id, reason);
    state.reload();
    onChange();
  }
  return (
    <Async state={state} empty="댓글이 없습니다">
      {(rows) => (
        <div className="admin-comments">
          {rows.map((c) => (
            <div key={c.id} className={`admin-comment ${c.parent_id ? "reply" : ""}`}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="small">
                  {c.parent_id && "↳ "}<b>{c.author_name}</b> <span className="muted">({c.author}) · {dateTime(c.created_at)}</span>
                  {c.author_ban && <span className="badge red" style={{ marginLeft: 6 }}>제한 중</span>}
                </div>
                <div className={c.deleted ? "muted small" : ""}>{c.deleted ? "삭제된 댓글 (답글이 있어 자리만 남음)" : c.body}</div>
                {banFor === c.id && <BanPanel userId={c.author} name={c.author_name} onDone={() => { state.reload(); onChange(); }} />}
              </div>
              {!c.deleted && (
                <span style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                  <button className="btn sm" onClick={() => setBanFor(banFor === c.id ? null : c.id)}>{banFor === c.id ? "닫기" : "작성자 제한"}</button>
                  <button className="btn sm danger" onClick={() => remove(c)}>삭제</button>
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </Async>
  );
}

/** 게시판 관리: 글 내용 확인, 숨김/다시 보이기, 삭제. 공지는 '공지사항' 메뉴에서 쓰면 게시판 맨 위에 나온다. */
export default function BoardAdmin() {
  const state = useAsync(getAllPosts);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [onlyHidden, setOnlyHidden] = useState(false);
  const [open, setOpen] = useState(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0); // 제한 목록 새로고침용
  const changed = () => {
    setVersion((v) => v + 1);
    state.reload();
  };

  async function run(fn) {
    setError("");
    try {
      await fn();
      setOpen(null);
      setReason("");
      state.reload();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <>
    <BannedUsers version={version} onChange={changed} />
    <section className="card">
      <SectionHead
        title="게시판 관리"
        desc="숨긴 글은 사용자에게 보이지 않고, 숨김·삭제 사유는 작성자에게 알림으로 전달됩니다 · 공지는 '공지사항' 메뉴에서 작성"
      />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
        <select className="input" style={{ maxWidth: 140 }} value={cat} onChange={(e) => setCat(e.target.value)} aria-label="말머리">
          <option value="">전체 말머리</option>
          {BOARD_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </select>
        <input className="input" style={{ maxWidth: 240 }} placeholder="제목·작성자 검색" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="check" style={{ alignItems: "center" }}>
          <input type="checkbox" checked={onlyHidden} onChange={(e) => setOnlyHidden(e.target.checked)} /> 숨긴 글만
        </label>
      </div>
      <Async state={state} empty="글이 없습니다">
        {(rows) => {
          const shown = rows
            .filter((p) => !cat || p.category === cat)
            .filter((p) => !onlyHidden || p.hidden)
            .filter((p) => `${p.title}${p.author_name}${p.author}`.includes(q.trim()));
          return (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>#</th><th>말머리</th><th>제목</th><th>작성자</th><th>작성일</th><th className="r">조회</th><th>상태</th><th /></tr>
                </thead>
                <tbody>
                  {shown.map((p) => (
                    <Fragment key={p.id}>
                      <tr className={p.hidden ? "muted" : ""}>
                        <td className="muted small">{p.id}</td>
                        <td><span className="badge">{p.category}</span></td>
                        <td>{p.title}{p.images.length > 0 && " 📷"}{p.comment_count > 0 && <span className="muted small"> [{p.comment_count}]</span>}</td>
                        <td className="small">
                          {p.author_name} <span className="muted">({p.author})</span>
                          {p.author_ban && <span className="badge red" style={{ marginLeft: 4 }}>제한 중</span>}
                        </td>
                        <td className="small num">{dateTime(p.created_at)}</td>
                        <td className="r small num">{p.views}</td>
                        <td>{p.hidden ? <span className="badge red" title={p.hidden_reason}>숨김</span> : <span className="badge green">공개</span>}</td>
                        <td className="r">
                          <button className="btn sm" onClick={() => { setOpen(open === p.id ? null : p.id); setReason(""); setError(""); }}>
                            {open === p.id ? "닫기" : "관리"}
                          </button>
                        </td>
                      </tr>
                      {open === p.id && (
                        <tr>
                          <td colSpan={8} style={{ background: "#fafaf7" }}>
                            <div style={{ display: "grid", gap: 10 }}>
                              <div style={{ whiteSpace: "pre-wrap" }}>{p.body}</div>
                              {p.images.length > 0 && (
                                <div className="thumbs">
                                  {p.images.map((src) => <div key={src} className="thumb"><Photo src={src} alt="" /></div>)}
                                </div>
                              )}
                              {p.hidden && <div className="small muted">숨김 사유: {p.hidden_reason}</div>}
                              <input className="input" placeholder="사유 (숨김은 필수, 작성자에게 전달됨)" value={reason} onChange={(e) => setReason(e.target.value)} />
                              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                {!p.hidden && <a className="btn sm" href={`${SITE_URL}/board/${p.id}`} target="_blank" rel="noreferrer">사이트에서 보기 ↗</a>}
                                {p.hidden ? (
                                  <button className="btn sm" onClick={() => run(() => setPostHidden(p.id, false))}>다시 보이기</button>
                                ) : (
                                  <button className="btn sm" onClick={() => run(() => setPostHidden(p.id, true, reason))}>숨기기</button>
                                )}
                                <button className="btn sm danger" onClick={() => confirm("이 글을 완전히 삭제할까요?") && run(() => adminDeletePost(p.id, reason))}>삭제</button>
                              </div>
                              {error && <span className="hint error">{error}</span>}
                              <div className="admin-sub">
                                <b className="small">글쓴이 이용 제한</b>
                                <BanPanel userId={p.author} name={p.author_name} onDone={changed} />
                              </div>
                              <div className="admin-sub">
                                <b className="small">댓글 {p.comment_count}개</b>
                                <PostComments postId={p.id} onChange={changed} />
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }}
      </Async>
    </section>
    </>
  );
}
