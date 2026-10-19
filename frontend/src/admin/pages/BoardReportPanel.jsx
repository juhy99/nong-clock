import { useState } from "react";
import { deleteComment, getPostComments, getPostForAdmin, setPostHidden } from "../../api/board";
import { useAuth } from "../../components/AuthContext";
import { Async, useAsync } from "../../components/common";
import { SITE_URL } from "../siteUrl";
import BanPanel from "./BanPanel";

/** 신고된 게시글·댓글 내용 확인 + 바로 조치 (글 숨기기 / 댓글 삭제 / 작성자 이용 제한) */
export default function BoardReportPanel({ report }) {
  const { user } = useAuth();
  const [msg, setMsg] = useState("");
  const state = useAsync(async () => {
    const post = await getPostForAdmin(report.post_id);
    const comment = report.kind === "comment" ? (await getPostComments(post.id)).find((c) => c.id === report.target_id) ?? null : null;
    return { post, comment };
  }, [report.id]);
  const reason = `신고 처리 (${report.type})`;

  async function run(fn, done) {
    try {
      await fn();
      setMsg(done);
      state.reload();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <Async state={state}>
      {({ post, comment }) => {
        const authorName = report.kind === "comment" ? comment?.author_name : post.author_name;
        return (
          <div style={{ display: "grid", gap: 10 }}>
            <b>신고된 {report.kind === "comment" ? "댓글" : "게시글"}</b>
            {report.kind === "post" ? (
              <div className="quote">
                <b>{post.title}</b> {post.hidden && <span className="badge red">숨김</span>}
                <div className="small" style={{ whiteSpace: "pre-wrap" }}>{post.body}</div>
              </div>
            ) : comment ? (
              <div className="quote">
                <span className="small muted">'{post.title}' 글의 댓글 · {comment.author_name}</span>
                <div>{comment.deleted ? <span className="muted">삭제된 댓글</span> : comment.body}</div>
              </div>
            ) : (
              <div className="quote muted">이미 삭제된 댓글입니다.</div>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {!post.hidden && <a className="btn sm" href={`${SITE_URL}/board/${post.id}${report.kind === "comment" ? `#c${report.target_id}` : ""}`} target="_blank" rel="noreferrer">사이트에서 보기 ↗</a>}
              {report.kind === "post" && !post.hidden && (
                <button className="btn sm danger" onClick={() => run(() => setPostHidden(post.id, true, reason), "글을 숨겼습니다")}>글 숨기기</button>
              )}
              {report.kind === "comment" && comment && !comment.deleted && (
                <button className="btn sm danger" onClick={() => run(() => deleteComment(user, comment.id, reason), "댓글을 지웠습니다")}>댓글 삭제</button>
              )}
            </div>
            {report.target_user && <BanPanel userId={report.target_user} name={authorName ?? report.target_user} />}
            {msg && <span className="hint ok">{msg}</span>}
          </div>
        );
      }}
    </Async>
  );
}
