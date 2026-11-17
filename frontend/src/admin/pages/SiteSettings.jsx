import { useEffect, useState } from "react";
import { getAdminSite, saveAdminSite } from "../../api/adminOps";
import { Async, SectionHead, useAsync } from "../../components/common";
import { SITE_URL } from "../siteUrl";

/**
 * 사이트 설정 (11-17): 코드 수정 · 다시 배포 없이 사용자 사이트에 바로 반영 (Spring /api/admin/site → DB site_setting)
 * 공지 띠 · 점검 안내 띠(맨 위) · 팀 소개와 연락처(서비스 소개) · 게시판 금칙어
 */
function Form({ init, reload }) {
  const [f, setF] = useState(init);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setF(init), [init]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? String(e.target.checked) : e.target.value });
  const dirty = Object.keys(f).some((k) => f[k] !== init[k]);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const patch = Object.fromEntries(Object.keys(f).filter((k) => f[k] !== init[k]).map((k) => [k, f[k]]));
      await saveAdminSite(patch);
      setMsg({ ok: true, text: "저장했어요. 사용자 사이트에는 1분 안에 반영돼요" });
      reload();
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    } finally {
      setBusy(false);
    }
  }
  const band = (on, text, label, hint) => (
    <div className="field">
      <label><input type="checkbox" checked={f[on] === "true"} onChange={set(on)} /> <b>{label}</b> 켜기</label>
      <input className="input" value={f[text]} onChange={set(text)} maxLength={200} placeholder={hint} />
      <span className="hint">{f[text].length}/200{f[on] === "true" && !f[text].trim() ? " · 문장이 비어 있으면 띠가 안 보여요" : ""}</span>
    </div>
  );

  return (
    <form onSubmit={save} style={{ display: "grid", gap: 18 }}>
      <section className="card" style={{ display: "grid", gap: 14 }}>
        <SectionHead title="맨 위 안내 띠" desc="사용자 사이트 모든 화면 맨 위에 보여요" right={<a className="link small" href={`${SITE_URL}/`} target="_blank" rel="noreferrer">사용자 사이트에서 보기 ↗</a>} />
        {band("maintenance_on", "maintenance_text", "🛠️ 점검 안내", "예: 11/20(금) 새벽 2~4시 서버 점검으로 접속이 끊길 수 있어요")}
        {band("notice_on", "notice_text", "📢 공지", "예: 11/14 거래까지 반영한 새 예측이 올라왔어요")}
      </section>
      <section className="card" style={{ display: "grid", gap: 14 }}>
        <SectionHead title="팀 소개 · 연락처" desc="서비스 소개 화면의 '만든 사람들' · '문의하기'. 비워 두면 그 칸이 안 보여요" />
        <div className="field">
          <label htmlFor="s-team">만든 사람들 (한 줄에 한 명 · 이름 | 맡은 일)</label>
          <textarea id="s-team" className="input" rows={5} value={f.team_text} onChange={set("team_text")} maxLength={1000} placeholder={"홍길동 | 백엔드 · Spring Boot\n김농부 | 예측 모델"} />
        </div>
        <div className="two-col">
          <div className="field"><label htmlFor="s-mail">문의 이메일</label><input id="s-mail" className="input" type="email" value={f.contact_email} onChange={set("contact_email")} maxLength={100} /></div>
          <div className="field"><label htmlFor="s-phone">전화 (선택)</label><input id="s-phone" className="input" value={f.contact_phone} onChange={set("contact_phone")} maxLength={30} /></div>
        </div>
        <div className="field"><label htmlFor="s-hours">응대 시간 (선택)</label><input id="s-hours" className="input" value={f.contact_hours} onChange={set("contact_hours")} maxLength={60} placeholder="평일 10:00~18:00" /></div>
      </section>
      <section className="card" style={{ display: "grid", gap: 14 }}>
        <SectionHead title="게시판 금칙어" desc="회원이 쓰는 글 제목 · 내용 · 댓글에 이 낱말이 있으면 올리지 못해요 (띄어쓰기를 끼워 써도 찾음). 관리자 글은 검사하지 않아요" />
        <div className="field">
          <label htmlFor="s-ban">쉼표나 줄바꿈으로 나눠 넣기 (두 글자 이상)</label>
          <textarea id="s-ban" className="input" rows={4} value={f.banned_words} onChange={set("banned_words")} maxLength={2000} placeholder="대출문의, 도박" />
          <span className="hint">이미 올라온 글은 그대로예요 — 게시판 관리에서 숨기거나 지우세요</span>
        </div>
      </section>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <button className="btn primary" disabled={!dirty || busy}>저장</button>
        {msg && <span className={`hint ${msg.ok ? "ok" : "error"}`}>{msg.text}</span>}
      </div>
    </form>
  );
}

export default function SiteSettings() {
  const state = useAsync(getAdminSite);
  return (
    <>
      <h1>사이트 설정</h1>
      <Async state={state}>{(d) => <Form init={d} reload={state.reload} />}</Async>
    </>
  );
}
