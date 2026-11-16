import { createContext, useContext, useEffect, useState } from "react";
import { adminLogin, adminLogout, adminMe } from "../api/adminBoard";

/** 관리자 로그인 상태 (11-14) — 사용자 사이트 회원 로그인(AuthContext)과 따로. 서버 세션(GET /api/admin/me)으로 확인 */
const Ctx = createContext(null);

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(undefined); // undefined = 확인 중, null = 로그인 안 함
  const [error, setError] = useState("");
  useEffect(() => {
    adminMe().then(setAdmin, (e) => {
      setError(e.message);
      setAdmin(null);
    });
  }, []);
  const value = {
    admin,
    checkError: error,
    login: async (email, pw) => setAdmin(await adminLogin(email, pw)),
    logout: async () => {
      await adminLogout();
      setAdmin(null);
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAdminAuth = () => useContext(Ctx);
