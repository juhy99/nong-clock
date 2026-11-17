import { useState } from "react";
import { Navigate, NavLink, Outlet, Route, Routes } from "react-router-dom";
import { useAdminAuth } from "./AdminAuth";
import { clearImages } from "../mocks/images";
import { resetAll } from "../mocks/store";
import { SITE_URL } from "./siteUrl";
import AuctionsAdmin from "./pages/AuctionsAdmin";
import BoardAdmin from "./pages/BoardAdmin";
import Dashboard from "./pages/Dashboard";
import DataStatus from "./pages/DataStatus";
import Members from "./pages/Members";
import ModelPerformance from "./pages/ModelPerformance";
import { buildText } from "../api/admin";
import { BUILD } from "../api/collection";
import { AUCTION_ENABLED } from "../features";

const MENU = [
  ["", "📊 대시보드"],
  ["board", "📝 게시판 관리 · 공지"],
  ["members", "👥 회원 관리"],
  ...(AUCTION_ENABLED ? [["auctions", "🔨 경매 관리"]] : []),
  ["data", "📥 데이터 수집"],
  ["model", "📈 모델 성능"],
];

/** 관리자 로그인 (11-14): DB 표 admin 의 계정만 — 사용자 사이트 회원 계정으로는 못 들어옴 */
function AdminLogin() {
  const { login, checkError } = useAdminAuth();
  const [email, setEmail] = useState("");
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
        <div className="admin-brand"><img src="/logo-icon.png" alt="" /> NongClock <small>관리자</small></div>
        {checkError && <div className="banner small">⚠️ {checkError}</div>}
        <div className="field">
          <label htmlFor="a-email">관리자 이메일</label>
          <input id="a-email" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="a-pw">비밀번호</label>
          <input id="a-pw" className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required />
        </div>
        {error && <span className="hint error">{error}</span>}
        <button className="btn primary block">로그인</button>
        <a className="link small" href={`${SITE_URL}/`}>← NongClock 사용자 사이트로</a>
      </form>
    </div>
  );
}

function AdminLayout() {
  const { admin, logout } = useAdminAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="admin-shell">
      <aside className={`admin-side ${menuOpen ? "open" : ""}`}>
        <div className="admin-brand"><img src="/logo-icon.png" alt="" /> NongClock <small>관리자</small></div>
        <nav onClick={() => setMenuOpen(false)}>
          {MENU.map(([to, label]) => (
            <NavLink key={to} to={`/${to}`} end={to === ""}>{label}</NavLink>
          ))}
        </nav>
        {/* 11-17: 회원 관리가 실제 DB 로 바뀌어 예시 데이터는 경매(보류)에만 남음 → 경매를 켤 때만 보여 줌 */}
        {AUCTION_ENABLED && (
          <button
            className="btn sm danger"
            onClick={async () => {
              if (!confirm("이 브라우저의 경매 예시 데이터(입찰·사진)를 처음 상태로 되돌릴까요? 실제 DB(게시판·공지·회원)는 바뀌지 않아요")) return;
              resetAll();
              await clearImages().catch(() => {});
              location.href = "/admin/";
            }}
          >
            예시 데이터 초기화
          </button>
        )}
      </aside>
      <div className="admin-main">
        <header className="admin-top">
          <button className="btn sm admin-menu-btn" onClick={() => setMenuOpen(!menuOpen)} aria-label="메뉴">☰</button>
          <a className="link small" href={`${SITE_URL}/`} target="_blank" rel="noreferrer">사용자 사이트 열기 ↗</a>
          <span style={{ flex: 1 }} />
          {BUILD.sha && <span className="admin-version num" title={buildText()}>배포 {BUILD.sha}</span>}
          <span className="small">🛠️ <b>{admin.name}</b></span>
          <button className="btn sm" onClick={logout}>로그아웃</button>
        </header>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

/** 관리자만 들어올 수 있다 (admin 표 계정으로 로그인). Spring 이 모든 /api/admin 요청에서 권한을 다시 확인한다 */
export default function AdminApp() {
  const { admin } = useAdminAuth();
  if (admin === undefined) return <div className="admin-login"><div className="card state">관리자 로그인 확인 중…</div></div>;
  if (!admin) return <AdminLogin />;
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<Dashboard />} />
        {/* 신고·분쟁: 사용자 사이트에서 신고 기능을 뺐으므로 메뉴도 숨김 (코드는 남김) */}
        <Route path="reports" element={<Navigate to="/" replace />} />
        <Route path="board" element={<BoardAdmin />} />
        <Route path="notices" element={<Navigate to="/board" replace />} /> {/* 11-14: 공지는 게시판 관리에서 (말머리 "공지") */}
        <Route path="members" element={<Members />} />
        <Route path="auctions" element={AUCTION_ENABLED ? <AuctionsAdmin /> : <Navigate to="/" replace />} />
        <Route path="data" element={<DataStatus />} />
        <Route path="model" element={<ModelPerformance />} />
        <Route path="system" element={<Navigate to="/" replace />} />
        <Route path="*" element={<div className="card state">없는 메뉴입니다.</div>} />
      </Route>
    </Routes>
  );
}
