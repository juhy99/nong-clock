import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { isEmailTaken } from "../api/auth";
import { useAuth } from "../components/AuthContext";

const SIDO = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"];

const TERMS = [
  ["service", "[필수] 서비스 이용약관 동의", true],
  ["privacy", "[필수] 개인정보 수집·이용 동의", true],
  ["age", "[필수] 만 14세 이상입니다", true],
  ["marketing", "[선택] 가격 급등 알림·이벤트 소식 받기", false],
];

/** 010-1234-5678 형태로 자동 하이픈 */
const formatPhone = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length < 4) return d;
  if (d.length < 8) return `${d.slice(0, 3)}-${d.slice(3)}`;
  return `${d.slice(0, 3)}-${d.slice(3, 7)}-${d.slice(7)}`;
};

function validate(f) {
  const e = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) e.email = "올바른 이메일 형식이 아닙니다";
  else if (isEmailTaken(f.email)) e.email = "이미 가입된 이메일입니다";
  if (f.password.length < 8 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password)) e.password = "영문과 숫자를 섞어 8자 이상 입력하세요";
  if (f.password2 !== f.password) e.password2 = "비밀번호가 일치하지 않습니다";
  if (f.name.trim().length < 2) e.name = "이름을 2자 이상 입력하세요";
  if (!/^01\d-\d{3,4}-\d{4}$/.test(f.phone)) e.phone = "휴대폰 번호를 확인하세요 (예: 010-1234-5678)";
  if (!f.region) e.region = "지역을 선택하세요";
  if (f.type === "seller" && !f.farm_name.trim()) e.farm_name = "판매자는 농장(상호)명을 입력하세요";
  return e;
}

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [agree, setAgree] = useState({});
  const [f, setF] = useState({ type: "buyer", email: "", password: "", password2: "", name: "", phone: "", region: "", farm_name: "" });
  const [touched, setTouched] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const errors = validate(f);
  const requiredAgreed = TERMS.filter(([, , req]) => req).every(([k]) => agree[k]);
  const allAgreed = TERMS.every(([k]) => agree[k]);
  const set = (k) => (e) => setF({ ...f, [k]: k === "phone" ? formatPhone(e.target.value) : e.target.value });
  const blur = (k) => () => setTouched({ ...touched, [k]: true });
  const fieldErr = (k) => touched[k] && errors[k];

  async function submit(e) {
    e.preventDefault();
    setTouched(Object.fromEntries(Object.keys(f).map((k) => [k, true])));
    if (Object.keys(errors).length) return;
    setBusy(true);
    try {
      await signup({ ...f, marketing: !!agree.marketing });
      nav("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const input = (k, label, props = {}) => (
    <div className="field">
      <label htmlFor={k}>{label}</label>
      <input id={k} className={`input ${fieldErr(k) ? "invalid" : ""}`} value={f[k]} onChange={set(k)} onBlur={blur(k)} {...props} />
      {fieldErr(k) ? <span className="hint error">{errors[k]}</span> : props.hint && <span className="hint">{props.hint}</span>}
    </div>
  );

  return (
    <div className="auth-wrap">
      <div className="card">
        <div className="steps"><span className="on" /><span className={step === 2 ? "on" : ""} /></div>
        {step === 1 ? (
          <div style={{ display: "grid", gap: 16 }}>
            <h1>회원가입</h1>
            <div className="field">
              <label>회원 유형</label>
              <div className="type-choice">
                {[["buyer", "🛒 구매자", "경매 입찰 · 시세 알림"], ["seller", "🧑‍🌾 판매자(농가)", "경매 상품 등록 · 판매"]].map(([k, t, d]) => (
                  <button key={k} type="button" className={f.type === k ? "on" : ""} onClick={() => setF({ ...f, type: k })}>
                    <b>{t}</b>
                    <div className="muted small">{d}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="field">
              <label>약관 동의</label>
              <label className="check" style={{ fontWeight: 700 }}>
                <input type="checkbox" checked={allAgreed} onChange={(e) => setAgree(Object.fromEntries(TERMS.map(([k]) => [k, e.target.checked])))} />
                전체 동의
              </label>
              {TERMS.map(([k, label]) => (
                <label key={k} className="check">
                  <input type="checkbox" checked={!!agree[k]} onChange={(e) => setAgree({ ...agree, [k]: e.target.checked })} />
                  {label}
                </label>
              ))}
            </div>
            <button className="btn primary block" disabled={!requiredAgreed} onClick={() => setStep(2)}>다음</button>
            <p className="muted small" style={{ margin: 0, textAlign: "center" }}>
              이미 회원이신가요? <Link to="/login" className="link">로그인</Link>
            </p>
          </div>
        ) : (
          <form onSubmit={submit} style={{ display: "grid", gap: 14 }} noValidate>
            <h1>정보 입력</h1>
            <p className="muted small" style={{ margin: 0 }}>{f.type === "seller" ? "🧑‍🌾 판매자(농가)" : "🛒 구매자"}로 가입합니다.</p>
            {input("email", "이메일", { type: "email", autoComplete: "email" })}
            {input("password", "비밀번호", { type: "password", autoComplete: "new-password", hint: "영문+숫자 8자 이상" })}
            {input("password2", "비밀번호 확인", { type: "password", autoComplete: "new-password" })}
            {input("name", "이름", { autoComplete: "name" })}
            {input("phone", "휴대폰 번호", { inputMode: "numeric", placeholder: "010-1234-5678" })}
            <div className="field">
              <label htmlFor="region">{f.type === "seller" ? "농장 소재지" : "지역"}</label>
              <select id="region" className={`input ${fieldErr("region") ? "invalid" : ""}`} value={f.region} onChange={set("region")} onBlur={blur("region")}>
                <option value="">선택하세요</option>
                {SIDO.map((s) => <option key={s}>{s}</option>)}
              </select>
              {fieldErr("region") && <span className="hint error">{errors.region}</span>}
            </div>
            {f.type === "seller" && input("farm_name", "농장(상호)명", { placeholder: "예: 이천 햇살농장" })}
            {error && <span className="hint error">{error}</span>}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn" onClick={() => setStep(1)}>이전</button>
              <button className="btn primary" style={{ flex: 1 }} disabled={busy}>가입하기</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
