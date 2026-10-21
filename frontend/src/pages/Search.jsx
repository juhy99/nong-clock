import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getMarketCompare, getTodayPrices } from "../api/market";
import { getItems, predict } from "../api/ml";
import { NEWS_PAGE_SIZE, getNews } from "../api/news";
import { recentSearches, removeRecentSearch, saveRecentSearch, searchAll } from "../api/search";
import { useAuth } from "../components/AuthContext";
import { Async, Highlight, PctChange, PriceChange, useAsync } from "../components/common";
import ForecastChart from "../components/ForecastChart";
import ItemImage from "../components/ItemImage";
import { NewsArticle, NewsRow, NewsSource, NewsUpdated } from "../components/NewsParts";
import { AuctionCard } from "./Auctions";
import { boardDate, md, won, wonPerKg } from "../utils/format";

const PREVIEW = { auctions: 3, news: 4, posts: 4 }; // "전체" 탭에서 미리 보여주는 개수
const FORECAST_DAYS = 14;

/** 검색한 품목 요약: 오늘 시세 + 2주 AI 예측 */
function ItemSummary({ item, p }) {
  const { user, updateProfile } = useAuth();
  const today = useAsync(getTodayPrices);
  const row = today.data?.items.find((x) => x.item === item.code);
  const fav = user?.favorites?.includes(item.code);
  const toggleFav = () =>
    updateProfile({ favorites: fav ? user.favorites.filter((c) => c !== item.code) : [...(user.favorites ?? []), item.code] });

  return (
    <section className={`search-item tone-${item.category}`}>
      <span className="search-item-img"><ItemImage code={item.code} emoji={item.emoji} alt={item.name} /></span>
      <div className="search-item-info">
        <div className="name">{item.name} <span className="cat">{item.category}</span></div>
        {row && (
          <div className="kpis">
            <div>
              <div className="muted small">오늘 도매 시세</div>
              <div className="v num">{won(row.price)}원<small>/kg</small></div>
              <PriceChange change={row.change} changePct={row.change_pct} comparedDate={today.data.compared_date} className="small" />
            </div>
            <div>
              <div className="muted small">소매가</div>
              <div className="v num">{won(row.retail_price)}원<small>/kg</small></div>
              <span className="muted small">도매가보다 {row.margin_pct}% 비싸요</span>
            </div>
          </div>
        )}
        <div className="acts">
          <Link className="btn primary sm" to={`/market?item=${item.code}`}>📈 시세 자세히</Link>
          <Link className="btn sm" to={`/ai?item=${item.code}`}>🤖 AI 예측</Link>
          {user ? (
            <button className={`btn sm ${fav ? "fav-on" : ""}`} onClick={toggleFav}>{fav ? "♥ 관심 품목" : "♡ 관심 품목"}</button>
          ) : (
            <Link className="btn sm" to="/login">♡ 관심 품목</Link>
          )}
        </div>
      </div>
      <div className="search-item-chart">
        {p ? (
          <>
            <div className="small muted">최근 시세 + AI 예측 {FORECAST_DAYS}일</div>
            <ForecastChart p={p} height={150} legend={false} />
            <div className="ai-line small">
              🤖 {FORECAST_DAYS}일 뒤 <b>{wonPerKg(p.predicted_price)}</b> 예상 (<PctChange value={p.change_pct} />)
            </div>
          </>
        ) : (
          <div className="state">예측 불러오는 중…</div>
        )}
      </div>
    </section>
  );
}

/** 오른쪽 칸: 이상기후·시장별 시세·관심 품목 */
function ItemSide({ item, p }) {
  const mkt = useAsync(() => getMarketCompare(item.code), [item.code]);
  const alert = p?.alerts[0];
  return (
    <aside className="search-side">
      {alert && (
        <div className="search-box warn">
          <h3>⚠️ 이상기후 주의</h3>
          <p className="small" style={{ margin: 0 }}>{md(alert.start)}~{md(alert.end)} — {alert.reason}. 이 기간 {item.name} 예측은 오차가 커질 수 있어요.</p>
        </div>
      )}
      {mkt.data && (
        <div className="search-box">
          <h3>시장별 오늘 시세</h3>
          <table className="table">
            <tbody>
              {mkt.data.markets.map((m) => (
                <tr key={m.market}><td>{m.market}</td><td className="r num"><b>{won(m.price)}</b>원/kg</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="search-box">
        <h3>{item.name} 소식 받기</h3>
        <p className="muted small" style={{ margin: "0 0 10px" }}>관심 품목에 넣으면 경매·이상기후 알림을 받고, 농업 뉴스에서 모아 볼 수 있어요.</p>
        <Link className="link" to={`/news?item=${item.code}`}>📰 {item.name} 뉴스 모아 보기 ›</Link>
      </div>
    </aside>
  );
}

function SecHead({ title, count, more, onMore, extra }) {
  return (
    <div className="search-sec-head">
      <h2>{title} <small>{count}건</small>{extra}</h2>
      {more && <button className="link" onClick={onMore}>{title} {count}건 모두 보기 ›</button>}
    </div>
  );
}

function PostList({ rows, q }) {
  return (
    <div className="search-list">
      {rows.map((p) => (
        <Link key={p.id} to={`/board/${p.id}`} className="search-post">
          <span className="tt">
            <span className="badge">{p.category}</span> <Highlight text={p.title} q={q} />
            {p.comment_count > 0 && <span className="cmt-count">[{p.comment_count}]</span>}
          </span>
          {p.snippet && <span className="sn"><Highlight text={p.snippet} q={q} /></span>}
          <span className="muted small">{p.author_name} · {boardDate(p.created_at)} · 조회 {p.views}</span>
        </Link>
      ))}
    </div>
  );
}

function NoticeList({ rows, q }) {
  return (
    <div className="search-list">
      {rows.map((n) => (
        <Link key={n.id} to={`/board/notice/${n.id}`} className="search-post">
          <span className="tt"><span className="badge amber">공지</span> <Highlight text={n.title} q={q} /></span>
          <span className="sn"><Highlight text={n.body} q={q} /></span>
        </Link>
      ))}
    </div>
  );
}

/** 뉴스 탭: 기사를 15개씩 더 불러온다 */
function NewsTab({ q, qItem }) {
  const [size, setSize] = useState(NEWS_PAGE_SIZE);
  const news = useAsync(() => getNews({ q, qItem, size }), [q, qItem, size]);
  return (
    <Async state={news} minHeight={200}>
      {(d) => (
        <>
          {d.rows.map((n) => <NewsArticle key={n.id} n={n} q={q} />)}
          {d.total > d.rows.length && (
            <div className="news-more"><button className="btn" onClick={() => setSize(size + NEWS_PAGE_SIZE)}>기사 더 보기 ({d.rows.length}/{d.total})</button></div>
          )}
          <NewsSource />
        </>
      )}
    </Async>
  );
}

function Empty({ q, suggestion }) {
  const items = useAsync(getItems);
  return (
    <div className="search-empty">
      <div style={{ fontSize: 40 }}>🔍</div>
      <h2>'{q}' 검색 결과가 없어요</h2>
      {suggestion && (
        <p>혹시 <Link className="link" to={`/search?q=${encodeURIComponent(suggestion)}`}>'{suggestion}'</Link>을(를) 찾으셨나요?</p>
      )}
      <p className="muted">팜비드에서 다루는 품목은 {items.data?.length ?? 16}가지예요</p>
      <div className="pills" style={{ justifyContent: "center" }}>
        {(items.data ?? []).map((i) => (
          <Link key={i.code} className="pill sm" to={`/search?q=${encodeURIComponent(i.name)}`}>
            <ItemImage code={i.code} emoji={i.emoji} className="xs" /> {i.name}
          </Link>
        ))}
      </div>
    </div>
  );
}

function Results({ d, tab, setTab }) {
  const { q, item } = d;
  const forecast = useAsync(() => (item ? predict({ item: item.code, horizon: FORECAST_DAYS }) : Promise.resolve(null)), [item?.code]);
  const p = forecast.data;
  const all = tab === "all";
  const tabs = [
    ["all", "전체", null],
    ["item", "시세·예측", item ? 1 : 0],
    ["auctions", "경매", d.auctions.length],
    ["news", "뉴스", d.news.total],
    ["posts", "게시판", d.posts.total],
    ["notices", "공지", d.notices.length],
  ];

  return (
    <>
      <div className="tabs" role="tablist">
        {tabs.map(([key, label, n]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "on" : ""} onClick={() => setTab(key)}>
            {label}{n != null && <small className="tab-n">{n}</small>}
          </button>
        ))}
      </div>

      <div className={item && (all || tab === "item") ? "search-layout" : ""}>
        <div className="search-main">
          {item && (all || tab === "item") && <ItemSummary item={item} p={p} />}
          {tab === "item" && !item && <div className="state">'{q}'은(는) 팜비드 품목이 아니에요. 품목 이름(예: 사과, 배추)으로 검색하면 시세와 예측을 보여드려요.</div>}

          {(all ? d.auctions.length > 0 : tab === "auctions") && (
            <section>
              <SecHead title="경매" count={d.auctions.length} more={all && d.auctions.length > PREVIEW.auctions} onMore={() => setTab("auctions")} />
              {d.auctions.length ? (
                <div className="grid search-auctions">
                  {(all ? d.auctions.slice(0, PREVIEW.auctions) : d.auctions).map((a) => <AuctionCard key={a.id} a={a} />)}
                </div>
              ) : (
                <div className="state">'{q}' 경매가 없어요</div>
              )}
            </section>
          )}

          {all && d.news.total > 0 && (
            <section>
              <SecHead title="뉴스" count={d.news.total} more={d.news.total > PREVIEW.news} onMore={() => setTab("news")} extra={<NewsUpdated at={d.news.updated_at} />} />
              <div className="news-list">{d.news.rows.slice(0, PREVIEW.news).map((n) => <NewsRow key={n.id} n={n} q={q} />)}</div>
              <p className="muted small" style={{ margin: "8px 0 0" }}>제목을 누르면 언론사 기사로 이동해요 · 뉴스 제공: 네이버 검색 API · 각 언론사</p>
            </section>
          )}
          {tab === "news" && (
            <section>
              <SecHead title="뉴스" count={d.news.total} extra={<NewsUpdated at={d.news.updated_at} />} />
              <NewsTab q={q} qItem={item?.code} />
            </section>
          )}

          {(all ? d.posts.total > 0 : tab === "posts") && (
            <section>
              <SecHead title="게시판" count={d.posts.total} more={all && d.posts.total > PREVIEW.posts} onMore={() => setTab("posts")} />
              {d.posts.total ? <PostList rows={all ? d.posts.rows.slice(0, PREVIEW.posts) : d.posts.rows} q={q} /> : <div className="state">'{q}' 게시글이 없어요</div>}
              {!all && d.posts.total > d.posts.rows.length && (
                <Link className="link" to={`/board?q=${encodeURIComponent(q)}`}>게시판에서 나머지 {d.posts.total - d.posts.rows.length}건 더 보기 ›</Link>
              )}
            </section>
          )}

          {(all ? d.notices.length > 0 : tab === "notices") && (
            <section>
              <SecHead title="공지" count={d.notices.length} />
              {d.notices.length ? <NoticeList rows={d.notices} q={q} /> : <div className="state">'{q}' 공지가 없어요</div>}
            </section>
          )}
        </div>
        {item && (all || tab === "item") && <ItemSide item={item} p={p} />}
      </div>
    </>
  );
}

export default function Search() {
  const [params, setParams] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const tab = params.get("tab") ?? "all";
  const [recent, setRecent] = useState(recentSearches);
  const state = useAsync(() => (q ? searchAll(q) : Promise.resolve(null)), [q]);
  const items = useAsync(getItems);

  useEffect(() => {
    if (q) setRecent(saveRecentSearch(q));
  }, [q]);

  const setTab = (t) => {
    setParams(t === "all" ? { q } : { q, tab: t });
    window.scrollTo({ top: 0 });
  };
  const d = state.data;
  // 함께 찾는 품목: 같은 분류의 다른 품목
  const related = d?.item ? (items.data ?? []).filter((i) => i.category === d.item.category && i.code !== d.item.code).slice(0, 3) : [];
  const otherRecent = recent.filter((r) => r !== q);

  if (!q) {
    return (
      <div className="page">
        <div className="page-head"><h1>검색</h1><p>위 검색창에 품목 이름이나 궁금한 단어를 넣어 보세요. 시세·예측·경매·뉴스·게시판을 한 번에 찾아 드려요.</p></div>
      </div>
    );
  }

  return (
    <div className="page search-page">
      <div className="search-head">
        <h1>'<em>{q}</em>' 검색 결과</h1>
        {d && d.total > 0 && (
          <span className="muted">
            {[d.item && "품목 1", `경매 ${d.auctions.length}`, `뉴스 ${d.news.total}`, `게시글 ${d.posts.total}`, `공지 ${d.notices.length}`].filter(Boolean).join(" · ")}
          </span>
        )}
      </div>
      {(related.length > 0 || otherRecent.length > 0) && (
        <div className="search-related">
          {related.length > 0 && (
            <>
              <span className="muted small">함께 찾는 품목</span>
              {related.map((i) => (
                <Link key={i.code} className="pill sm" to={`/search?q=${encodeURIComponent(i.name)}`}><ItemImage code={i.code} emoji={i.emoji} className="xs" /> {i.name}</Link>
              ))}
            </>
          )}
          {otherRecent.length > 0 && (
            <>
              <span className="muted small">최근 검색</span>
              {otherRecent.map((r) => (
                <span key={r} className="pill sm recent">
                  <Link to={`/search?q=${encodeURIComponent(r)}`}>{r}</Link>
                  <button aria-label={`최근 검색어 ${r} 지우기`} onClick={() => setRecent(removeRecentSearch(r))}>✕</button>
                </span>
              ))}
            </>
          )}
        </div>
      )}
      <Async state={state} minHeight={300}>
        {(data) => (data.total === 0 ? <Empty q={q} suggestion={data.suggestion} /> : <Results d={data} tab={tab} setTab={setTab} />)}
      </Async>
    </div>
  );
}
