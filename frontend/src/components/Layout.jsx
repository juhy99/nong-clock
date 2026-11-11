import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { DATA_SOURCE, ML_API_BASE, NEWS_URL } from "../api/client";
import { onMlOffline } from "../api/ml";
import { AUCTION_ENABLED } from "../features";
import { recommendLink, suggest } from "../api/search";
import { USER_TYPE_LABEL, useAuth } from "./AuthContext";
import { Highlight } from "./common";
import ItemImage from "./ItemImage";
import NotificationBell from "./NotificationBell";

// 가격 예측 · 작물 추천 (헤더 강조 버튼 · 휴대폰 아래 고정 바)
export const CORE = [
  ["/ai", "🤖", "가격 예측", "언제 팔까"],
  ["/recommend", "🌱", "작물 추천", "무엇을 심을까"],
];

/** 휴대폰: 화면 아래 고정 바 — 가격 예측 · 작물 추천 */
function CoreDock() {
  return (
    <nav className="core-dock" aria-label="가격 예측 · 작물 추천">
      {CORE.map(([to, icon, label, q]) => (
        <NavLink key={to} to={to} className={`core ${to.slice(1)}`}>
          <span className="ic">{icon}</span>
          <span><b>{label}</b><small>{q}</small></span>
        </NavLink>
      ))}
    </nav>
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
  const empty = hints && !hints.items.length && !hints.crops.length && !hints.auctions.length && !hints.posts.length && !hints.news.length;
  // 목록을 누르는 동안 입력창의 blur 로 닫히지 않게
  const keep = (e) => e.preventDefault();

  return (
    <form className="search" role="search" onSubmit={submit} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      <span aria-hidden>🔍</span>
      <input
        placeholder={AUCTION_ENABLED ? "품목·경매·뉴스·게시글 검색" : "품목·뉴스·게시글 검색"}
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
          {hints.crops.length > 0 && <div className="g">작물 추천</div>}
          {hints.crops.map((c) => (
            <button type="button" key={`crop-${c.code}`} className="o" onClick={() => go(recommendLink(c.code))}>
              <span className="e">{c.emoji}</span>
              <b><Highlight text={c.name} q={q} /></b>
              <small>작물 정보 ›</small>
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

/** 머리말 (v17): 로고 · 검색 · 메뉴(HOME·가격 예측·작물 추천·시세·뉴스·게시판) · 로그인 / 내 정보.
 *  홈 첫 화면 위에서는 반투명, 스크롤하면 흰 띠(solid). 서비스 소개는 바닥글에서 들어감 */
function Header() {
  const { user, isAdmin, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [solid, setSolid] = useState(false);
  // 휴대폰 메뉴 (☰): 다른 화면으로 가면 닫힘
  const [menu, setMenu] = useState(false);
  useEffect(() => setMenu(false), [loc.pathname, loc.search]);
  useEffect(() => {
    const on = () => setSolid(window.scrollY > 10);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [loc.pathname]);
  const links = [
    ["/", "HOME"],
    ["/ai", "가격 예측"],
    ["/recommend", "작물 추천"],
    ["/market", "시세"],
    ...(AUCTION_ENABLED ? [["/auctions", "경매"]] : []),
    ["/news", "뉴스"],
    ["/board", "게시판"],
  ];
  const out = () => {
    logout();
    nav("/");
  };
  return (
    <header className={`header ${solid || menu ? "solid" : ""}`}>
      <div className="container header-inner">
        <Link to="/" className="logo">
          <img src="/logo-nongclock.png" alt="NongClock" />
        </Link>
        <HeaderSearch />
        <nav className="top-nav" aria-label="주 메뉴">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
          ))}
        </nav>
        <div className="header-right">
          {user ? (
            <>
              {/* 관리자 화면은 별도 사이트 (/admin/) */}
              {isAdmin && <a className="btn sm hdr-admin" href="/admin/" target="_blank" rel="noreferrer">관리자 사이트 ↗</a>}
              <NotificationBell user={user} />
              <NavLink to="/mypage" className="user-chip" title={`${user.name} · ${USER_TYPE_LABEL[user.type]}`}>
                <b>{user.name}</b> <span className="muted">· 마이페이지</span>
              </NavLink>
              <button className="btn sm ghost hdr-out" onClick={out}>
                로그아웃
              </button>
            </>
          ) : (
            <Link to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} className="btn sm login">로그인</Link>
          )}
          <button type="button" className="hdr-menu" aria-label={menu ? "메뉴 닫기" : "메뉴 열기"} aria-expanded={menu} onClick={() => setMenu((m) => !m)}>
            {menu ? "✕" : "☰"}
          </button>
        </div>
      </div>
      {/* 휴대폰 메뉴: 검색 · 모든 메뉴 · 마이페이지/로그아웃 (넓은 화면에서는 안 보임) */}
      {menu && (
        <div className="hdr-drawer">
          <HeaderSearch />
          <nav aria-label="휴대폰 메뉴">
            {links.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
            ))}
          </nav>
          {user && (
            <div className="hdr-user">
              <NavLink to="/mypage">👤 <b>{user.name}</b> · 마이페이지</NavLink>
              {isAdmin && <a href="/admin/" target="_blank" rel="noreferrer">관리자 사이트 ↗</a>}
              <button type="button" className="btn sm ghost" onClick={out}>로그아웃</button>
            </div>
          )}
        </div>
      )}
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
        <span>ℹ️</span>
        {/* 글자를 한 덩어리로 묶어야 휴대폰에서 줄마다 세로로 쪼개지지 않음 */}
        <div className="banner-txt">
          ML API({ML_API_BASE})에 연결할 수 없어 AI 예측을 <b>데모 데이터</b>로 보여주고 있습니다. ml-api 폴더에서
          <code> python -m uvicorn app.main:app --reload </code>로 서버를 켜면 실제 API 응답으로 바뀝니다.
        </div>
      </div>
    </div>
  );
}

/** 개발 중(npm run dev)에만: 어떤 데이터가 진짜인지 왼쪽 아래에 표시 */
const DEV_BADGE = import.meta.env.DEV && (() => {
  const parts = [];
  if (DATA_SOURCE === "live") parts.push(NEWS_URL ? "날씨 실제 데이터" : "날씨·뉴스 실제 데이터");
  if (NEWS_URL) parts.push("뉴스 서버 수집");
  return parts.length ? `테스트 모드 · ${parts.join(" · ")}` : null;
})();

export default function Layout() {
  const { pathname } = useLocation();
  const home = pathname === "/";
  return (
    <>
      {/* 배경 밭 사진: 홈은 첫 화면이 직접 그림(또렷하게), 나머지 화면은 흐리게 깔아 글씨가 잘 보이게 */}
      {!home && <div className="farm-bg blur" aria-hidden><i /></div>}
      <Header />
      {/* 홈은 첫 화면 사진이 머리말 뒤까지 깔려야 해서 ML API 안내 줄을 넣지 않음 (카드는 데모 값으로 그대로 보임) */}
      {!home && <OfflineBanner />}
      {home ? <Outlet /> : (
        <main className="container">
          <Outlet />
        </main>
      )}
      {DEV_BADGE && <div className="live-badge" title="frontend/.env 의 VITE_DATA_SOURCE · VITE_NEWS_URL. 나머지는 가짜 데이터">{DEV_BADGE}</div>}
      <footer className={`footer ${home ? "light" : ""}`}>
        <span>© NongClock · 공영도매시장 경매 · KAMIS · 기상청 데이터</span>
        <span className="r">
          <Link to="/about">서비스 소개</Link>
          <Link to="/about#contact">문의</Link>
        </span>
      </footer>
      <CoreDock />
    </>
  );
}
