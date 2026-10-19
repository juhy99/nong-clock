import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BOARD_CATEGORIES, createPost, getPost, updatePost } from "../../api/board";
import { MAX_IMAGES, uploadImages } from "../../api/upload";
import { useAuth } from "../../components/AuthContext";
import ImagePicker from "../../components/ImagePicker";
import Photo from "../../components/Photo";

/** 글쓰기 / 글 수정 (주소에 :id 가 있으면 수정) */
export default function PostWrite() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ category: "", title: "", body: "" });
  const [kept, setKept] = useState([]); // 수정할 때 남겨 둘 기존 사진 주소
  const [files, setFiles] = useState([]); // 새로 고른 사진
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    getPost(id)
      .then((p) => {
        if (p.author !== user.id) throw new Error("본인 글만 고칠 수 있습니다");
        setF({ category: p.category, title: p.title, body: p.body });
        setKept(p.images);
      })
      .catch((e) => setError(e.message));
  }, [id, user.id]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const images = [...kept, ...(await uploadImages(files))];
      const p = id ? await updatePost(user, id, { ...f, images }) : await createPost(user, { ...f, images });
      nav(`/board/${p.id}`, { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <Link to={id ? `/board/${id}` : "/board"} className="link">← {id ? "글로 돌아가기" : "게시판"}</Link>
      <h1>{id ? "글 수정" : "글쓰기"}</h1>
      <form className="card" style={{ display: "grid", gap: 14 }} onSubmit={submit}>
        <div className="write-row">
          <select className="input" aria-label="말머리" value={f.category} onChange={set("category")} style={{ maxWidth: 160 }}>
            <option value="">말머리 선택</option>
            {BOARD_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <input className="input" aria-label="제목" placeholder="제목" maxLength={80} value={f.title} onChange={set("title")} />
        </div>
        <textarea className="input" aria-label="내용" rows={12} placeholder="내용을 입력하세요" value={f.body} onChange={set("body")} />
        <div className="field">
          <label>사진 <span className="muted small">(선택, 최대 {MAX_IMAGES}장)</span></label>
          {kept.length > 0 && (
            <div className="thumbs">
              {kept.map((src, i) => (
                <div key={src} className="thumb">
                  <Photo src={src} alt={`기존 사진 ${i + 1}`} />
                  <button type="button" aria-label={`기존 사진 ${i + 1} 빼기`} onClick={() => setKept(kept.filter((x) => x !== src))}>×</button>
                </div>
              ))}
            </div>
          )}
          <ImagePicker files={files} onChange={setFiles} max={MAX_IMAGES - kept.length} />
        </div>
        {error && <span className="hint error">{error}</span>}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Link className="btn" to={id ? `/board/${id}` : "/board"}>취소</Link>
          <button className="btn primary" disabled={busy}>{id ? "수정하기" : "등록하기"}</button>
        </div>
      </form>
    </div>
  );
}
