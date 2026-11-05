import { Link, useNavigate } from "react-router-dom";
import { getNotices } from "../api/admin";
import { getAuctions } from "../api/auction";
import { getItems, getTopMovers } from "../api/ml";
import { BottomLists, CoreFeatures, IndexCards, MarketBoard } from "./HomeDashboard";
import { getTodayPrices } from "../api/market";
import { getNews, getNewsTrend } from "../api/news";
import { useAuth } from "../components/AuthContext";
import { Async, useAsync } from "../components/common";
import { NewsRow, NewsTrend, NewsUpdated } from "../components/NewsParts";
import WeatherMap from "../components/WeatherMap";
import { AuctionCard } from "./Auctions";
import { AUCTION_ENABLED } from "../features";

function NoticeBanner() {
  const { data } = useAsync(getNotices);
  const shown = data?.filter((n) => n.show_on_home) ?? [];
  if (!shown.length) return null;
  return shown.map((n) => (
    <div key={n.id} className="banner">
      ⚠️
      <div>
        <b>{n.title}</b> — {n.body}
      </div>
    </div>
  ));
}

/** 오늘의 농업 뉴스: 헤드라인만, 누르면 언론사 기사로 */
function NewsHeadlines() {
  const { user } = useAuth();
  const nav = useNavigate();
  const favorites = user?.favorites ?? [];
  const news = useAsync(() => getNews({ size: 6 }));
  const trend = useAsync(() => getNewsTrend({ days: 7, limit: 5 }));
  const mine = useAsync(() => (favorites.length ? getNews({ items: favorites, size: 3 }) : Promise.resolve(null)), [favorites.join()]);
  return (
    <section>
      <div className="sec-head">
        <div>
          <h2>오늘의 농업 뉴스</h2>
          <p>
            팜비드 품목 관련 기사 · 제목을 누르면 언론사 기사로 이동해요
            {news.data && <> · <NewsUpdated at={news.data.updated_at} /></>}
          </p>
        </div>
        <Link className="link" to="/news">뉴스 더 보기 →</Link>
      </div>
      <div className="home-news">
        <div className="news-list boxed">
          <Async state={news} minHeight={240}>
            {(d) => d.rows.map((n) => <NewsRow key={n.id} n={n} />)}
          </Async>
        </div>
        <div className="home-news-side">
          <div className="news-box">
            <h3>이번 주 뉴스에 많이 나온 품목</h3>
            <p className="muted small">누르면 그 품목 기사만 모아 봐요</p>
            {trend.data && <NewsTrend rows={trend.data} onPick={(c) => nav(`/news?item=${c}`)} />}
          </div>
          <div className="news-box line">
            <h3>내 관심 품목 뉴스</h3>
            {!user && <p className="muted small"><Link className="link" to="/login">로그인</Link>하면 관심 품목 기사만 모아 보여줘요</p>}
            {user && !favorites.length && <p className="muted small">마이페이지 › 관심 품목을 고르면 여기에 기사가 모여요</p>}
            {mine.data?.rows.map((n) => {
              const tag = n.item_tags.find((t) => favorites.includes(t.item));
              return (
                <a key={n.id} className="mine-row" href={n.url} target="_blank" rel="noreferrer">
                  <span className="news-item-tag">{tag?.emoji} {tag?.name}</span>
                  <span className="t">{n.title}</span>
                </a>
              );
            })}
            {mine.data && !mine.data.rows.length && <p className="muted small">아직 관심 품목 기사가 없어요</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function PopularAuctions() {
  const state = useAsync(() => getAuctions({ sort: "popular" }));
  return (
    <section>
      <div className="sec-head">
        <div>
          <h2>🔥 지금 뜨거운 경매</h2>
          <p>농가가 직접 올린 상품 · 입찰이 몰리는 순</p>
        </div>
        <Link className="link" to="/auctions">전체 보기 →</Link>
      </div>
      <Async state={state} empty="진행 중인 경매가 없습니다">
        {(rows) => (
          <div className="grid auction-grid">
            {rows.slice(0, 4).map((a) => <AuctionCard key={a.id} a={a} />)}
          </div>
        )}
      </Async>
    </section>
  );
}

export default function Home() {
  // 30일 뒤 예측(107품목)·오늘 시세는 여러 칸이 같이 쓰므로 한 번만 불러온다
  const movers = useAsync(() => getTopMovers({ horizon: 30, limit: 107 }));
  const today = useAsync(getTodayPrices);
  const items = useAsync(getItems);
  const shared = { movers: movers.data, today: today.data, items: items.data };
  return (
    <div className="page">
      <NoticeBanner />
      {/* 가격 예측·작물 추천 → 지수 → 품목 차트·순위 → AI 상승·하락·관심 품목 → 뉴스·날씨 */}
      <CoreFeatures {...shared} />
      <IndexCards {...shared} />
      <MarketBoard {...shared} />
      <BottomLists {...shared} />
      <NewsHeadlines />
      <WeatherMap />
      {AUCTION_ENABLED && <PopularAuctions />}
    </div>
  );
}
