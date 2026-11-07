import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { checkDuplicate } from "../api/auth";
import { useAuth } from "../components/AuthContext";
import { SIDO, formatPhone } from "../utils/format";
import { AUCTION_ENABLED } from "../features";

// 약관 동의 단계 없이 바로 정보 입력 (11-07 결정). 이메일·닉네임은 [중복 확인] 을 눌러 통과해야 가입할 수 있다
function validate(f, checked) {
  const e = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email)) e.email = "올바른 이메일 형식이 아닙니다";
  else if (checked.email !== f.email.trim().toLowerCase()) e.email = "이메일 중복 확인을 눌러 주세요";
  if (f.password.length < 8 || !/[A-Za-z]/.test(f.password) || !/\d/.test(f.password)) e.password = "영문과 숫자를 섞어 8자 이상 입력하세요";
  if (f.password2 !== f.password) e.password2 = "비밀번호가 일치하지 않습니다";
  if (f.nickname.trim().length < 2 || f.nickname.trim().length > 20) e.nickname = "닉네임은 2~20자로 입력하세요";
  else if (checked.nickname !== f.nickname.trim().toLowerCase()) e.nickname = "닉네임 중복 확인을 눌러 주세요";
  if (!/^01\d-\d{3,4}-\d{4}$/.test(f.phone)) e.phone = "휴대폰 번호를 확인하세요 (예: 010-1234-5678)";
  if (!f.region) e.region = "지역을 선택하세요";
  return e;
}

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ email: "", password: "", password2: "", nickname: "", phone: "", region: "", farm_name: "" });
  const [touched, setTouched] = useState({});
  const [checked, setChecked] = useState({}); // { email: "통과한 값", nickname: "통과한 값" }
  const [dup, setDup] = useState({}); // { email: { ok, msg } }
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const errors = validate(f, checked);
  const set = (k) => (e) => {
    setF({ ...f, [k]: k === "phone" ? formatPhone(e.target.value) : e.target.value });
    if (k === "email" || k === "nickname") setDup({ ...dup, [k]: null });
  };
  const blur = (k) => () => setTouched({ ...touched, [k]: true });
  const fieldErr = (k) => touched[k] && !dup[k]?.msg && errors[k];

  async function check(k) {
    const v = f[k].trim();
    if (k === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) return setDup({ ...dup, email: { ok: false, msg: "올바른 이메일 형식이 아닙니다" } });
    if (k === "nickname" && (v.length < 2 || v.length > 20)) return setDup({ ...dup, nickname: { ok: false, msg: "닉네임은 2~20자로 입력하세요" } });
    try {
      const taken = await checkDuplicate(k, v);
      const label = k === "email" ? "이메일" : "닉네임";
      setDup({ ...dup, [k]: taken ? { ok: false, msg: `이미 사용 중인 ${label}이에요` } : { ok: true, msg: `사용할 수 있는 ${label}이에요` } });
      setChecked({ ...checked, [k]: taken ? null : v.toLowerCase() });
    } catch (err) {
      setDup({ ...dup, [k]: { ok: false, msg: err.message } });
    }
  }

  async function submit(e) {
    e.preventDefault();
    setTouched(Object.fromEntries(Object.keys(f).map((k) => [k, true])));
    if (Object.keys(errors).length) return;
    setBusy(true);
    try {
      await signup({ ...f, name: f.nickname.trim() });
      nav("/", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const input = (k, label, props = {}, withCheck = false) => (
    <div className="field">
      <label htmlFor={k}>{label}</label>
      <div className={withCheck ? "dup-row" : undefined}>
        <input id={k} className={`input ${fieldErr(k) || dup[k]?.ok === false ? "invalid" : ""}`} value={f[k]} onChange={set(k)} onBlur={blur(k)} {...props} />
        {withCheck && <button type="button" className={`btn ${dup[k]?.ok ? "ok" : ""}`} onClick={() => check(k)}>{dup[k]?.ok ? "✓ 확인됨" : "중복 확인"}</button>}
      </div>
      {dup[k]?.msg ? <span className={`hint ${dup[k].ok ? "ok" : "error"}`}>{dup[k].msg}</span>
        : fieldErr(k) ? <span className="hint error">{errors[k]}</span> : props.hint && <span className="hint">{props.hint}</span>}
    </div>
  );

  return (
    <div className="auth-wrap">
      <div className="card">
        <form onSubmit={submit} style={{ display: "grid", gap: 14 }} noValidate>
          <h1>회원가입</h1>
          {AUCTION_ENABLED && <p className="muted small" style={{ margin: 0 }}>가입하면 경매 입찰과 상품 판매(경매 등록)를 모두 할 수 있어요.</p>}
          {input("email", "이메일", { type: "email", autoComplete: "email" }, true)}
          {input("password", "비밀번호", { type: "password", autoComplete: "new-password", hint: "영문+숫자 8자 이상" })}
          {input("password2", "비밀번호 확인", { type: "password", autoComplete: "new-password" })}
          {input("nickname", "닉네임", { autoComplete: "nickname", hint: "게시판·댓글에 보이는 이름 (2~20자)" }, true)}
          {input("phone", "휴대폰 번호", { inputMode: "numeric", placeholder: "010-1234-5678" })}
          <div className="field">
            <label htmlFor="region">지역</label>
            <select id="region" className={`input ${fieldErr("region") ? "invalid" : ""}`} value={f.region} onChange={set("region")} onBlur={blur("region")}>
              <option value="">선택하세요</option>
              {SIDO.map((s) => <option key={s}>{s}</option>)}
            </select>
            {fieldErr("region") && <span className="hint error">{errors.region}</span>}
          </div>
          {input("farm_name", "농장·상호명 (선택)", { placeholder: "예: 이천 햇살농장", hint: AUCTION_ENABLED ? "경매에 판매자 이름으로 함께 표시돼요" : undefined })}
          {error && <span className="hint error">{error}</span>}
          <button className="btn primary block" disabled={busy}>가입하기</button>
          <p className="muted small" style={{ margin: 0, textAlign: "center" }}>
            이미 회원이신가요? <Link to="/login" className="link">로그인</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
