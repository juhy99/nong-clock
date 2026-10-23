import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { changePassword, withdrawBlockers } from "../../api/auth";
import { useAuth } from "../../components/AuthContext";
import { SectionHead } from "../../components/common";
import { DEFAULT_NOTIFY, NOTIFY_TYPES } from "../../mocks/notifications";
import { SIDO, formatPhone } from "../../utils/format";

function InfoForm() {
  const { user, updateProfile } = useAuth();
  const [f, setF] = useState({ name: user.name, phone: user.phone, region: user.region, farm_name: user.farm_name ?? "" });
  const [notify, setNotify] = useState({ ...DEFAULT_NOTIFY, ...user.notify });
  const [msg, setMsg] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: k === "phone" ? formatPhone(e.target.value) : e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (f.name.trim().length < 2) return setMsg({ ok: false, text: "이름을 2자 이상 입력하세요" });
    if (!/^01\d-\d{3,4}-\d{4}$/.test(f.phone)) return setMsg({ ok: false, text: "휴대폰 번호를 확인하세요 (예: 010-1234-5678)" });
    try {
      await updateProfile({ ...f, name: f.name.trim(), notify });
      setMsg({ ok: true, text: "저장했습니다" });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  return (
    <form className="card" style={{ display: "grid", gap: 14 }} onSubmit={submit}>
      <SectionHead title="내 정보 수정" desc="이메일과 회원 유형은 바꿀 수 없어요" />
      <div className="two-col">
        <div className="field">
          <label htmlFor="p-name">이름</label>
          <input id="p-name" className="input" value={f.name} onChange={set("name")} />
        </div>
        <div className="field">
          <label>이메일</label>
          <input className="input" value={user.email} disabled style={{ background: "#f4f3ef" }} />
        </div>
      </div>
      <div className="two-col">
        <div className="field">
          <label htmlFor="p-phone">연락처</label>
          <input id="p-phone" className="input" value={f.phone} onChange={set("phone")} inputMode="numeric" />
        </div>
        <div className="field">
          <label htmlFor="p-region">지역</label>
          <select id="p-region" className="input" value={f.region} onChange={set("region")}>
            {SIDO.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor="p-farm">농장·상호명 <span className="muted small">(선택, 경매 판매자 이름으로 표시)</span></label>
        <input id="p-farm" className="input" value={f.farm_name} onChange={set("farm_name")} />
      </div>
      <div className="field">
        <label>알림 받기</label>
        <div className="pills">
          {Object.entries(NOTIFY_TYPES).map(([k, t]) => (
            <button type="button" key={k} className={`pill ${notify[k] ? "on" : ""}`} onClick={() => setNotify({ ...notify, [k]: !notify[k] })}>
              {t.icon} {t.label}
            </button>
          ))}
        </div>
        <span className="hint">끈 종류의 알림은 종 아이콘으로 오지 않아요</span>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "flex-end" }}>
        {msg && <span className={`hint ${msg.ok ? "ok" : "error"}`}>{msg.text}</span>}
        <button className="btn primary">저장</button>
      </div>
    </form>
  );
}

function PasswordForm() {
  const { user } = useAuth();
  const [f, setF] = useState({ current: "", next: "", next2: "" });
  const [msg, setMsg] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (f.next !== f.next2) return setMsg({ ok: false, text: "새 비밀번호가 서로 다릅니다" });
    try {
      await changePassword(user.id, f.current, f.next);
      setF({ current: "", next: "", next2: "" });
      setMsg({ ok: true, text: "비밀번호를 바꿨습니다" });
    } catch (err) {
      setMsg({ ok: false, text: err.message });
    }
  }

  return (
    <form className="card" style={{ display: "grid", gap: 12 }} onSubmit={submit}>
      <SectionHead title="비밀번호 변경" />
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        <input className="input" type="password" placeholder="현재 비밀번호" value={f.current} onChange={set("current")} autoComplete="current-password" required />
        <input className="input" type="password" placeholder="새 비밀번호 (영문+숫자 8자 이상)" value={f.next} onChange={set("next")} autoComplete="new-password" required />
        <input className="input" type="password" placeholder="새 비밀번호 확인" value={f.next2} onChange={set("next2")} autoComplete="new-password" required />
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", justifyContent: "flex-end" }}>
        {msg && <span className={`hint ${msg.ok ? "ok" : "error"}`}>{msg.text}</span>}
        <button className="btn">비밀번호 변경</button>
      </div>
    </form>
  );
}

function Withdraw() {
  const { user, withdraw } = useAuth();
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const blockers = withdrawBlockers(user.id);

  async function submit(e) {
    e.preventDefault();
    if (!confirm("정말 탈퇴할까요? 탈퇴하면 같은 이메일로 다시 가입할 수 없어요.")) return;
    try {
      await withdraw(pw);
      nav("/", { replace: true });
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="card danger-zone" style={{ display: "grid", gap: 10 }} onSubmit={submit}>
      <h3 style={{ color: "var(--danger)" }}>회원 탈퇴</h3>
      <p className="muted small" style={{ margin: 0 }}>
        탈퇴하면 관심 품목과 알림이 사라지고 로그인할 수 없어요. 지난 낙찰·거래 기록은 분쟁 처리를 위해 보관돼요.
        <br />
        <b>진행 중인 내 경매나 최고가로 입찰 중인 경매가 있으면 탈퇴할 수 없어요.</b>
      </p>
      {blockers.length > 0 && (
        <div className="banner small">
          ⚠️
          <div>{blockers.join(", ")}이 있어요. 경매가 끝나거나 취소한 뒤 탈퇴할 수 있어요.</div>
        </div>
      )}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <input className="input" type="password" placeholder="비밀번호 확인" value={pw} onChange={(e) => setPw(e.target.value)} style={{ maxWidth: 260 }} required />
        <button className="btn danger" disabled={blockers.length > 0}>탈퇴하기</button>
      </div>
      {error && <span className="hint error">{error}</span>}
    </form>
  );
}

export default function Profile() {
  return (
    <>
      <InfoForm />
      <PasswordForm />
      <Withdraw />
    </>
  );
}
