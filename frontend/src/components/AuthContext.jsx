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

/** 로그인이 필요한 페이지 감싸개 (관리자 화면은 별도 사이트 src/admin 에서 따로 확인) */
export function RequireAuth({ children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return children;
}

export const USER_TYPE_LABEL = { buyer: "구매자", seller: "판매자(농가)", admin: "관리자" };
