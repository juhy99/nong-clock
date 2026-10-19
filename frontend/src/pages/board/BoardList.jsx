import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { getNotices } from "../../api/admin";
import { BOARD_CATEGORIES, getPosts } from "../../api/board";
import { useAuth } from "../../components/AuthContext";
import { useAsync } from "../../components/common";
import { boardDate } from "../../utils/format";

export default function BoardList() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const q = params.get("q") ?? "";
  const page = Number(params.get("page") ?? 1);
  const [keyword, setKeyword] = useState(q);

  const go = (patch) => {
    const next = { category, q, page: 1, ...patch };
    // 기본값(전체, 검색어 없음, 1쪽)은 주소에서 뺀다
    setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v && v !== 1)));
  };
  const notices = useAsync(getNotices);
  const state = useAsync(() => getPosts({ category, q, page }), [category, q, page]);

  return (
    <div className="page">
      <div className="page-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h1>게시판</h1>
          <p>시세 정보, 재배 노하우, 거래 후기를 나눠요</p>
        </div>
        <button className="btn primary" onClick={() => nav(user ? "/board/write" : "/login?next=/board/write")}>✏️ 글쓰기</button>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <div className="pills">
          {["", ...BOARD_CATEGORIES].map((c) => (
            <button key={c || "all"} className={`pill ${category === c ? "on" : ""}`} onClick={() => go({ category: c })}>
              {c || "전체"}
            </button>
          ))}
        </div>
        <form
          style={{ display: "flex", gap: 6 }}
          onSubmit={(e) => {
            e.preventDefault();
            go({ q: keyword.trim() });
          }}
        >
          <input className="input" style={{ width: 200 }} placeholder="제목·내용·작성자 검색" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
          <button className="btn">검색</button>
        </form>
      </div>

      <section className="card" style={{ padding: 0, overflow: "hidden" }}>
        <table className="table board-table">
          <thead>
            <tr>
              <th className="col-no">번호</th>
              <th className="col-cat">말머리</th>
              <th>제목</th>
              <th className="col-author">작성자</th>
              <th className="col-date">작성일</th>
              <th className="col-views r">조회</th>
            </tr>
          </thead>
          <tbody>
            {/* 공지는 항상 맨 위 (검색·필터·페이지와 상관없이) */}
            {(notices.data ?? []).map((n) => (
              <tr key={`n${n.id}`} className="notice-row">
                <td className="col-no"><span className="badge red">공지</span></td>
                <td className="col-cat small">{n.category}</td>
                <td>
                  <Link className="post-title" to={`/board/notice/${n.id}`}>
                    <span className="cat-inline badge red">공지</span>
                    <b>{n.title}</b>
                  </Link>
                </td>
                <td className="col-author small">관리자</td>
                <td className="col-date small num">{boardDate(n.created_at)}</td>
                <td className="col-views r small muted">-</td>
              </tr>
            ))}
            {state.data?.rows.map((p) => (
              <tr key={p.id}>
                <td className="col-no muted small num">{p.id}</td>
                <td className="col-cat"><span className="badge">{p.category}</span></td>
                <td>
                  <Link className="post-title" to={`/board/${p.id}`}>
                    <span className="cat-inline badge">{p.category}</span>
                    {p.title}
                    {p.images.length > 0 && <span title="사진 있음"> 📷</span>}
                  </Link>
                  <div className="post-meta small muted">{p.author_name} · {boardDate(p.created_at)} · 조회 {p.views}</div>
                </td>
                <td className="col-author small">{p.author_name}</td>
                <td className="col-date small num">{boardDate(p.created_at)}</td>
                <td className="col-views r small num">{p.views}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {state.loading && !state.data && <div className="state">불러오는 중…</div>}
        {state.error && <div className="state error">{state.error.message}</div>}
        {state.data?.rows.length === 0 && (
          <div className="state">{q ? `'${q}' 검색 결과가 없습니다` : "아직 글이 없습니다. 첫 글을 남겨 보세요!"}</div>
        )}
      </section>

      {state.data && state.data.pages > 1 && (
        <nav className="pager" aria-label="페이지">
          <button className="btn sm" disabled={state.data.page === 1} onClick={() => go({ page: state.data.page - 1 })}>이전</button>
          {Array.from({ length: state.data.pages }, (_, i) => i + 1).map((n) => (
            <button key={n} className={`btn sm ${n === state.data.page ? "primary" : ""}`} onClick={() => go({ page: n })}>{n}</button>
          ))}
          <button className="btn sm" disabled={state.data.page === state.data.pages} onClick={() => go({ page: state.data.page + 1 })}>다음</button>
        </nav>
      )}
    </div>
  );
}
