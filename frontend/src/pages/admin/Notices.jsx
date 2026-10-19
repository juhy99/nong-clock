import { useState } from "react";
import { deleteNotice, getNotices, saveNotice } from "../../api/admin";
import { NOTICE_CATEGORIES } from "../../mocks/admin";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime } from "../../utils/format";

const EMPTY = { category: "일반", title: "", body: "", pinned: false, show_on_home: false, sendNotification: false };

export default function Notices() {
  const state = useAsync(getNotices);
  const [form, setForm] = useState(EMPTY);
  const editing = !!form.id;

  async function submit(e) {
    e.preventDefault();
    if (!form.title.trim()) return;
    await saveNotice(form);
    setForm(EMPTY);
    state.reload();
  }

  return (
    <>
      <section className="card">
        <SectionHead title={editing ? "공지 수정" : "새 공지 작성"} desc="서비스 점검 · 가격 급등 안내 · 정책 공지. '홈 배너'를 켜면 홈 화면 상단에 노출됩니다." />
        <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 10 }}>
            <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {NOTICE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
            <input className="input" placeholder="제목" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
          </div>
          <textarea className="input" rows={3} placeholder="내용" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
            <label className="check"><input type="checkbox" checked={form.pinned} onChange={(e) => setForm({ ...form, pinned: e.target.checked })} /> 상단 고정</label>
            <label className="check"><input type="checkbox" checked={form.show_on_home} onChange={(e) => setForm({ ...form, show_on_home: e.target.checked })} /> 홈 배너로 노출</label>
            <label className="check"><input type="checkbox" checked={!!form.sendNotification} onChange={(e) => setForm({ ...form, sendNotification: e.target.checked })} /> 회원 전체에게 알림 보내기</label>
            <div style={{ flex: 1 }} />
            {editing && <button type="button" className="btn" onClick={() => setForm(EMPTY)}>취소</button>}
            <button className="btn primary">{editing ? "수정 저장" : "등록"}</button>
          </div>
        </form>
      </section>
      <section className="card">
        <SectionHead title="공지 목록" />
        <Async state={state} empty="등록된 공지가 없습니다">
          {(rows) => (
            <table className="table">
              <thead>
                <tr><th>분류</th><th>제목</th><th>노출</th><th>작성</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((n) => (
                  <tr key={n.id}>
                    <td><span className="badge">{n.category}</span></td>
                    <td>{n.pinned && "📌 "}<b>{n.title}</b><div className="muted small">{n.body}</div></td>
                    <td>{n.show_on_home ? <span className="badge green">홈 배너</span> : <span className="muted small">목록만</span>}</td>
                    <td className="small num">{dateTime(n.created_at)}</td>
                    <td className="r" style={{ whiteSpace: "nowrap" }}>
                      <button className="btn sm" onClick={() => setForm(n)}>수정</button>{" "}
                      <button className="btn sm danger" onClick={async () => { if (confirm("삭제할까요?")) { await deleteNotice(n.id); state.reload(); } }}>삭제</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Async>
      </section>
    </>
  );
}
