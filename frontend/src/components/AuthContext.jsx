import { createContext, useContext, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
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

/** 로그인(또는 관리자)이 필요한 페이지 감싸개 */
export function RequireAuth({ admin = false, children }) {
  const { user, isAdmin } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (admin && !isAdmin)
    return (
      <div className="container page">
        <div className="card state error">관리자만 볼 수 있는 페이지입니다.</div>
      </div>
    );
  return children;
}

export const USER_TYPE_LABEL = { buyer: "구매자", seller: "판매자(농가)", admin: "관리자" };
