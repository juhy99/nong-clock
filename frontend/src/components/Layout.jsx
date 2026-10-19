import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { getTodayPrices } from "../api/market";
import { ML_API_BASE } from "../api/client";
import { onMlOffline } from "../api/ml";
import { pct, won } from "../utils/format";
import { USER_TYPE_LABEL, useAuth } from "./AuthContext";
import { useAsync } from "./common";

function Ticker() {
  const { data } = useAsync(getTodayPrices);
  if (!data) return <div className="ticker" style={{ height: 34 }} />;
  const row = data.items.map((p) => (
    <span key={p.item}>
      <b>{p.name}</b>
      {won(p.price)}원/kg{" "}
      <span style={{ color: p.change > 0 ? "#ff6b6b" : p.change < 0 ? "#6ea8ff" : "#aaa" }}>
        {p.change > 0 ? "▲" : p.change < 0 ? "▼" : "-"} {pct(p.change_pct)}
      </span>
    </span>
  ));
  // 끊김 없이 흐르도록 같은 목록을 두 번 붙인다
  return (
    <div className="ticker" aria-label="오늘의 시세">
      <div className="ticker-track">
        {row}
        {row}
      </div>
    </div>
  );
}

function Header() {
  const { user, isAdmin, logout } = useAuth();
  const nav = useNavigate();
  const links = [
    ["/", "홈"],
    ["/market", "시세·수급"],
    ["/ai", "AI 가격예측"],
    ["/auctions", "경매 마켓"],
    ["/mypage", "마이페이지"],
    ...(isAdmin ? [["/admin", "개발자"]] : []),
  ];
  return (
    <header className="header">
      <div className="container header-inner">
        <Link to="/" className="logo">
          🌱 FarmBid<small>팜비드</small>
        </Link>
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="header-right">
          {user ? (
            <>
              <span className="user-chip">
                👤 {user.name} <span className="muted">· {USER_TYPE_LABEL[user.type]}</span>
              </span>
              <button
                className="btn sm"
                onClick={() => {
                  logout();
                  nav("/");
                }}
              >
                로그아웃
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="btn sm">로그인</Link>
              <Link to="/signup" className="btn sm primary">회원가입</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function OfflineBanner() {
  const [offline, setOffline] = useState(false);
  useEffect(() => onMlOffline(setOffline), []);
  if (!offline) return null;
  return (
    <div className="container" style={{ paddingTop: 14 }}>
      <div className="banner info small">
        ℹ️ ML API({ML_API_BASE})에 연결할 수 없어 AI 예측을 <b>데모 데이터</b>로 보여주고 있습니다. ml-api 폴더에서
        <code> python -m uvicorn app.main:app --reload </code>로 서버를 켜면 실제 API 응답으로 바뀝니다.
      </div>
    </div>
  );
}

export default function Layout() {
  return (
    <>
      <Ticker />
      <Header />
      <OfflineBanner />
      <main className="container">
        <Outlet />
      </main>
      <footer className="footer">
        FarmBid · 시세·경매·회원 데이터는 개발용 가상 데이터입니다 (실서비스 연동 시 KAMIS·aT 도매시장 API)
      </footer>
    </>
  );
}
