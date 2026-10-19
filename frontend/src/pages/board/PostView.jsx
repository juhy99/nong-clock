import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getNotices } from "../../api/admin";
import { deletePost, getPost } from "../../api/board";
import { useAuth } from "../../components/AuthContext";
import { Async, useAsync } from "../../components/common";
import Photo from "../../components/Photo";
import ReportModal from "../../components/ReportModal";
import Comments from "./Comments";
import { dateTime } from "../../utils/format";

function Article({ badge, title, meta, body, images = [], actions }) {
  return (
    <article className="card post">
      <div className="post-head">
        <div>
          {badge}
          <h1 style={{ marginTop: 8 }}>{title}</h1>
          <div className="muted small" style={{ marginTop: 6 }}>{meta}</div>
        </div>
        {actions}
      </div>
      <div className="post-body">{body}</div>
      {images.length > 0 && (
        <div className="post-images">
          {images.map((src, i) => <Photo key={src} src={src} alt={`첨부 사진 ${i + 1}`} />)}
        </div>
      )}
    </article>
  );
}

export function PostView() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const state = useAsync(() => getPost(id, { countView: true }), [id]);
  const [reporting, setReporting] = useState(false);

  async function remove(p) {
    if (!confirm("이 글을 지울까요?")) return;
    await deletePost(user, p.id);
    nav("/board", { replace: true });
  }

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <Link to="/board" className="link">← 게시판</Link>
      <Async state={state}>
        {(p) => (
          <>
            <Article
              badge={<span className="badge">{p.category}</span>}
              title={p.title}
              meta={`${p.author_name} · ${dateTime(p.created_at)}${p.updated_at ? " (수정됨)" : ""} · 조회 ${p.views}`}
              body={p.body}
              images={p.images}
              actions={
                user?.id === p.author ? (
                  <div style={{ display: "flex", gap: 6 }}>
                    <Link className="btn sm" to={`/board/${p.id}/edit`}>수정</Link>
                    <button className="btn sm danger" onClick={() => remove(p)}>삭제</button>
                  </div>
                ) : (
                  user && <button className="btn sm danger" onClick={() => setReporting(true)}>🚨 신고</button>
                )
              }
            />
            <Comments post={p} />
            {reporting && <ReportModal target={{ kind: "post", id: p.id, label: p.title, post_id: p.id }} onClose={() => setReporting(false)} />}
          </>
        )}
      </Async>
    </div>
  );
}

export function NoticeView() {
  const { id } = useParams();
  const state = useAsync(async () => {
    const n = (await getNotices()).find((x) => x.id === Number(id));
    if (!n) throw new Error("삭제된 공지입니다");
    return n;
  }, [id]);
  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <Link to="/board" className="link">← 게시판</Link>
      <Async state={state}>
        {(n) => (
          <Article
            badge={<><span className="badge red">공지</span> <span className="badge">{n.category}</span></>}
            title={n.title}
            meta={`관리자 · ${dateTime(n.created_at)}`}
            body={n.body}
          />
        )}
      </Async>
    </div>
  );
}
