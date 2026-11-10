import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../components/AuthContext";
import { AUTH_MODE } from "../api/auth";
import { useErrorPopup } from "../components/ErrorPopup";

const DEMO = [
  ["김구매", "user@farmbid.kr", "user1234"],
  ["박농부", "farmer@farmbid.kr", "farmer1234"],
  ["관리자", "admin@farmbid.kr", "admin1234"],
];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const showError = useErrorPopup();
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, pw);
      nav(params.get("next") || "/", { replace: true });
    } catch (err) {
      showError(err, { title: "로그인하지 못했어요", login: false, hints: { 401: "이메일과 비밀번호를 다시 확인해 주세요. 영문 대소문자도 구분해요." } });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <form className="card" onSubmit={submit} style={{ display: "grid", gap: 14 }}>
        <h1>로그인</h1>
        <div className="field">
          <label htmlFor="email">이메일</label>
          <input id="email" className="input" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="pw">비밀번호</label>
          <input id="pw" className="input" type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required />
        </div>
        <button className="btn primary block" disabled={busy}>로그인</button>
        <p className="muted small" style={{ margin: 0, textAlign: "center" }}>
          아직 회원이 아니신가요? <Link to="/signup" className="link">회원가입</Link>
        </p>
      </form>
      {AUTH_MODE === "mock" && ( // 가짜 계정 모드에서만 (실제 회원 서버에 연결하면 숨김)
      <div className="banner info small" style={{ marginTop: 14, display: "block" }}>
        <b>개발용 데모 계정</b> (클릭하면 입력됩니다)
        <div className="pills" style={{ marginTop: 8 }}>
          {DEMO.map(([label, e, p]) => (
            <button key={e} type="button" className="pill" onClick={() => { setEmail(e); setPw(p); }}>{label}</button>
          ))}
        </div>
      </div>
      )}
    </div>
  );
}
