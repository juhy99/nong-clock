import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { getTodayPrices } from "../api/market";
import { ML_API_BASE } from "../api/client";
import { onMlOffline } from "../api/ml";
import { suggest } from "../api/search";
import { pct, won } from "../utils/format";
import { USER_TYPE_LABEL, useAuth } from "./AuthContext";
import { Highlight, useAsync } from "./common";
import ItemImage from "./ItemImage";
import NotificationBell from "./NotificationBell";

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

/**
 * 헤더 검색: 입력하는 동안 품목·경매·게시글·뉴스를 미리 보여주고, Enter 를 누르면 통합 검색 결과(/search?q=)로 간다.
 */
function HeaderSearch() {
  const nav = useNavigate();
  const loc = useLocation();
  const [params] = useSearchParams();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [hints, setHints] = useState(null);

  // 검색 결과 화면에서는 검색어를 그대로 보여준다
  const current = loc.pathname === "/search" ? params.get("q") ?? "" : "";
  useEffect(() => setQ(current), [current]);

  useEffect(() => {
    const word = q.trim();
    if (!word || word === current) {
      setHints(null);
      return;
    }
    let alive = true;
    const t = setTimeout(() => suggest(word).then((h) => alive && setHints(h)), 200);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, current]);

  function go(to) {
    setOpen(false);
    nav(to);
  }
  function submit(e) {
    e.preventDefault();
    const word = q.trim();
    if (word) go(`/search?q=${encodeURIComponent(word)}`);
  }
  const empty = hints && !hints.items.length && !hints.auctions.length && !hints.posts.length && !hints.news.length;
  // 목록을 누르는 동안 입력창의 blur 로 닫히지 않게
  const keep = (e) => e.preventDefault();

  return (
    <form className="search" role="search" onSubmit={submit} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <span aria-hidden>🔍</span>
      <input
        placeholder="품목·경매·뉴스·게시글 검색"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        aria-label="검색"
        aria-autocomplete="list"
      />
      <button>검색</button>
      {open && hints && (
        <div className="search-dd" onMouseDown={keep}>
          {hints.items.length > 0 && <div className="g">품목</div>}
          {hints.items.map((i) => (
            <button type="button" key={i.code} className="o" onClick={() => go(`/market?item=${i.code}`)}>
              <span className="e"><ItemImage code={i.code} emoji={i.emoji} className="xs" /></span>
              <b><Highlight text={i.name} q={q} /></b>
              <small>시세 바로가기 ›</small>
            </button>
          ))}
          {hints.auctions.length > 0 && <div className="g">경매</div>}
          {hints.auctions.map((a) => (
            <button type="button" key={a.id} className="o" onClick={() => go(`/auctions/${a.id}`)}>
              <span className="e">{a.emoji}</span>
              <span className="t"><Highlight text={a.title} q={q} /></span>
            </button>
          ))}
          {hints.posts.length > 0 && <div className="g">게시글</div>}
          {hints.posts.map((p) => (
            <button type="button" key={p.id} className="o" onClick={() => go(`/board/${p.id}`)}>
              <span className="e">📝</span>
              <span className="t"><Highlight text={p.title} q={q} /></span>
            </button>
          ))}
          {hints.news.length > 0 && <div className="g">뉴스</div>}
          {hints.news.map((n) => (
            <a key={n.id} className="o" href={n.url} target="_blank" rel="noreferrer" onClick={() => setOpen(false)}>
              <span className="e">📰</span>
              <span className="t"><Highlight text={n.title} q={q} /></span>
              <small>↗</small>
            </a>
          ))}
          {empty && <div className="g">바로 보여줄 결과가 없어요</div>}
          <button type="button" className="o all" onClick={submit}>'{q.trim()}' 전체 결과 보기 ›</button>
        </div>
      )}
    </form>
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
    ["/news", "농업 뉴스"],
    ["/board", "게시판"],
    ["/about", "서비스 소개"],
  ];
  return (
    <header className="header">
      <div className="container header-inner">
        <Link to="/" className="logo">
          🌱 FarmBid<small>팜비드</small>
        </Link>
        <HeaderSearch />
        <div className="header-right">
          {user ? (
            <>
              {/* 관리자 화면은 별도 사이트 (/admin/) */}
              {isAdmin && <a className="btn sm" href="/admin/" target="_blank" rel="noreferrer">관리자 사이트 ↗</a>}
              <NotificationBell user={user} />
              {/* 마이페이지는 로그인했을 때만, 오른쪽 끝에 */}
              <NavLink to="/mypage" className="user-chip" title={`${user.name} · ${USER_TYPE_LABEL[user.type]}`}>
                👤 <b>{user.name}</b> <span className="muted">· 마이페이지</span>
              </NavLink>
              <button
                className="btn sm ghost"
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
      <div className="container">
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              {label}
            </NavLink>
          ))}
        </nav>
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
        FarmBid · 시세·경매·회원 데이터는 개발용 가상 데이터입니다 (실서비스 연동 시 KAMIS·aT 도매시장 API) ·{" "}
        <Link to="/about" className="link small">서비스 소개 · 문의</Link>
      </footer>
    </>
  );
}
