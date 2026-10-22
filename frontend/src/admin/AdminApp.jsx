import { useState } from "react";
import { Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "../components/AuthContext";
import { clearImages } from "../mocks/images";
import { resetAll } from "../mocks/store";
import { SITE_URL } from "./siteUrl";
import AuctionsAdmin from "./pages/AuctionsAdmin";
import BoardAdmin from "./pages/BoardAdmin";
import Dashboard from "./pages/Dashboard";
import DataStatus from "./pages/DataStatus";
import Members from "./pages/Members";
import ModelPerformance from "./pages/ModelPerformance";
import Notices from "./pages/Notices";
import Reports from "./pages/Reports";
import { buildText } from "../api/admin";
import { BUILD } from "../api/collection";

const MENU = [
  ["", "📊 대시보드"],
  ["reports", "🚨 신고·분쟁"],
  ["board", "📝 게시판 관리"],
  ["notices", "📢 공지사항"],
  ["members", "👥 회원 관리"],
  ["auctions", "🔨 경매 관리"],
  ["data", "📥 데이터 수집"],
  ["model", "📈 모델 성능"],
];

function AdminLogin() {
  const { user, login, logout } = useAuth();
  const [email, setEmail] = useState("admin@farmbid.kr");
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    setError("");
    try {
      await login(email, pw);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="admin-login">
      <form className="card" onSubmit={submit}>
        <div className="admin-brand">🌱 FarmBid <small>관리자</small></div>
        {user && (
          <div className="banner small">
            ⚠️
            <div>
              <b>{user.name}</b>({user.email}) 계정은 관리자 권한이 없습니다.{" "}
              <button type="button" className="link" onClick={logout}>로그아웃</button>
            </div>
          </div>
        )}
        <div className="field">
          <label htmlFor="a-email">관리자 이메일</label>
          <input id="a-email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="a-pw">비밀번호</label>
          <input id="a-pw" className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="데모: admin1234" required />
        </div>
        {error && <span className="hint error">{error}</span>}
        <button className="btn primary block">로그인</button>
        <a className="link small" href={`${SITE_URL}/`}>← 팜비드 사용자 사이트로</a>
      </form>
    </div>
  );
}

function AdminLayout() {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="admin-shell">
      <aside className={`admin-side ${menuOpen ? "open" : ""}`}>
        <div className="admin-brand">🌱 FarmBid <small>관리자</small></div>
        <nav onClick={() => setMenuOpen(false)}>
          {MENU.map(([to, label]) => (
            <NavLink key={to} to={`/${to}`} end={to === ""}>{label}</NavLink>
          ))}
        </nav>
        <button
          className="btn sm danger"
          onClick={async () => {
            if (!confirm("가짜 데이터(회원가입·입찰·게시글·사진·신고 처리 기록)를 처음 상태로 되돌릴까요?")) return;
            resetAll();
            await clearImages().catch(() => {});
            location.href = "/admin/";
          }}
        >
          데모 데이터 초기화
        </button>
      </aside>
      <div className="admin-main">
        <header className="admin-top">
          <button className="btn sm admin-menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label="메뉴">☰</button>
          <a className="link small" href={`${SITE_URL}/`} target="_blank" rel="noreferrer">사용자 사이트 열기 ↗</a>
          <span style={{ flex: 1 }} />
          {BUILD.sha && <span className="admin-version num" title={buildText()}>배포 {BUILD.sha}</span>}
          <span className="small">🛠️ <b>{user.name}</b></span>
          <button className="btn sm" onClick={logout}>로그아웃</button>
        </header>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** 관리자만 들어올 수 있다. 실제로는 Spring 이 모든 /api/admin 요청에서 권한을 다시 확인해야 한다. */
export default function AdminApp() {
  const { user, isAdmin } = useAuth();
  if (!user || !isAdmin) return <AdminLogin />;
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="reports" element={<Reports />} />
        <Route path="board" element={<BoardAdmin />} />
        <Route path="notices" element={<Notices />} />
        <Route path="members" element={<Members />} />
        <Route path="auctions" element={<AuctionsAdmin />} />
        <Route path="data" element={<DataStatus />} />
        <Route path="model" element={<ModelPerformance />} />
        <Route path="system" element={<Navigate to="/" replace />} />
        <Route path="*" element={<div className="card state">없는 메뉴입니다.</div>} />
      </Route>
    </Routes>
  );
}
