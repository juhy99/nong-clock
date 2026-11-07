import { createContext, useContext, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import * as auth from "../api/auth";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => auth.getSession());
  const value = {
    user,
    isAdmin: user?.type === "admin",
    login: async (email, pw) => setUser(await auth.login(email, pw)),
    signup: async (form) => setUser(await auth.signup(form)),
    updateProfile: async (patch) => setUser(await auth.updateProfile(user.id, patch)),
    withdraw: async (password) => {
      await auth.withdraw(user.id, password);
      setUser(null);
    },
    logout: () => {
      auth.logout();
      setUser(null);
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);

/** 로그인이 필요한 페이지 감싸개 (관리자 화면은 별도 사이트 src/admin 에서 따로 확인) */
/** 로그인한 회원만: 로그인 전이면 화면 대신 안내 카드 (로그인·회원가입 버튼) */
export function MembersOnly({ title, children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (user) return children;
  const next = encodeURIComponent(loc.pathname + loc.search);
  return (
    <div className="page">
      <div className="card members-only">
        <div className="mo-ic" aria-hidden>🔒</div>
        <h1>{title}은(는) 회원 전용이에요</h1>
        <p className="muted">로그인하면 바로 이용할 수 있어요. 가입은 1분이면 끝나요.</p>
        <div className="mo-acts">
          <Link className="btn primary" to={`/login?next=${next}`}>로그인</Link>
          <Link className="btn" to="/signup">회원가입</Link>
        </div>
      </div>
    </div>
  );
}

export function RequireAuth({ children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return children;
}

// 회원 유형은 일반회원(member)과 관리자(admin) 두 가지. 일반회원은 누구나 입찰도 판매(경매 등록)도 할 수 있다.
// buyer·seller 는 예전 가짜 데이터에 남아 있을 수 있어서 같은 이름으로 보여준다.
export const USER_TYPE_LABEL = { member: "일반회원", buyer: "일반회원", seller: "일반회원", admin: "관리자" };

/** 경매 등록(판매)을 할 수 있는지: 관리자를 뺀 모든 회원 */
export const canSell = (user) => !!user && user.type !== "admin";
