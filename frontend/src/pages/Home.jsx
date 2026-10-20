import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getNotices } from "../api/admin";
import { getAuctions } from "../api/auction";
import { getHorizons, getItems, getTopMovers, predict } from "../api/ml";
import { getTodayPrices } from "../api/market";
import { getNews, getNewsTrend } from "../api/news";
import { useAuth } from "../components/AuthContext";
import { Async, PctChange, PriceChange, useAsync } from "../components/common";
import ItemImage from "../components/ItemImage";
import ForecastChart from "../components/ForecastChart";
import { NewsRow, NewsTrend, NewsUpdated } from "../components/NewsParts";
import WeatherMap from "../components/WeatherMap";
import { AuctionCard } from "./Auctions";
import { addDays, md, shortDate, todayIso, won, wonPerKg } from "../utils/format";

const HOME_PRICE_COUNT = 8; // 홈에는 일부만, 전체는 시세·수급 화면에서

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

function TodayPrices() {
  const state = useAsync(getTodayPrices);
  return (
    <section>
      <Async state={state} minHeight={260}>
        {(d) => (
          <>
            <div className="sec-head">
              <div>
                <h2>오늘의 주요 시세</h2>
                <p>{shortDate(d.base_date)} {d.market} 도매가 · 1kg 기준 · {shortDate(d.compared_date)} 대비</p>
              </div>
              <Link className="link" to="/market">전체 시세 →</Link>
            </div>
            <div className="grid price-grid">
              {d.items.slice(0, HOME_PRICE_COUNT).map((p) => (
                <Link key={p.item} to={`/market?item=${p.item}`} className="price-card">
                  <span className={`tile tone-${p.category ?? "기타"}`}>
                    <ItemImage code={p.item} emoji={p.emoji} alt={p.name} />
                  </span>
                  <span className="name">{p.name}</span>
                  <span className="price num">{won(p.price)}원<small>/kg</small></span>
                  <PriceChange change={p.change} changePct={p.change_pct} className="small" />
                </Link>
              ))}
            </div>
          </>
        )}
      </Async>
    </section>
  );
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

// 예측 기간 → 첫 화면 문장 ("다음 주 배추, 5.8% 내려갈 거예요")
const WHEN = { 7: "다음 주", 14: "2주 뒤", 30: "한 달 뒤" };

/** 홈 맨 위: AI 예측으로 본 앞으로의 가격 (품목·기간을 바꿔 가며 바로 확인) */
function ForecastHero() {
  const options = useAsync(async () => {
    const [items, horizons] = await Promise.all([getItems(), getHorizons()]);
    return { items, horizons };
  });
  const [horizon, setHorizon] = useState(null);
  const [picked, setPicked] = useState(null);
  const h = horizon ?? options.data?.horizons[0]?.days;
  const info = Object.fromEntries((options.data?.items ?? []).map((i) => [i.code, i]));

  const movers = useAsync(() => (h ? getTopMovers({ horizon: h, limit: 4 }) : Promise.resolve(null)), [h]);
  // 품목을 고르지 않았으면 가장 크게 움직일 품목을 먼저 보여준다
  const item = picked ?? movers.data?.[0]?.item;
  const result = useAsync(() => (item && h ? predict({ item, horizon: h }) : Promise.resolve(null)), [item, h]);
  const p = result.data;
  const dir = p ? (p.change_pct > 0 ? "up" : p.change_pct < 0 ? "down" : "flat") : "flat";
  const target = p?.forecast.at(-1)?.date;

  return (
    <section className="hero">
      <div>
        <span className="eyebrow">🤖 AI 가격 예측{p ? ` · ${shortDate(p.base_date)} 기준` : ""}</span>
        <h1>
          {p ? (
            <>
              {WHEN[h] ?? `${h}일 뒤`} {p.item_name},
              <br />
              {dir === "flat" ? (
                "지금과 비슷할 거예요"
              ) : (
                <>
                  <em className={dir}>{Math.abs(p.change_pct).toFixed(1)}% {dir === "up" ? "오를" : "내려갈"}</em> 거예요
                </>
              )}
            </>
          ) : (
            "AI가 앞으로의 가격을 알려드려요"
          )}
        </h1>
        <p className="lead">날씨·명절·과거 시세를 학습한 AI가 앞으로 30일의 전국 도매가를 매일 예측해요. 품목을 골라 보세요.</p>
        {options.data && (
          <div className="pills">
            {options.data.items.slice(0, 9).map((i) => (
              <button key={i.code} className={`pill ${item === i.code ? "on" : ""}`} onClick={() => setPicked(i.code)}>
                <ItemImage code={i.code} emoji={i.emoji} className="xs" /> {i.name}
              </button>
            ))}
            <Link className="pill" to="/ai">+{Math.max(0, options.data.items.length - 9)}</Link>
          </div>
        )}
      </div>
      <div className="hero-chart">
        <div className="row">
          <div className="hero-kpi">
            <div className="muted small">{p ? `${p.item_name} · ${shortDate(target)} 예상 도매가` : "예상 도매가"}</div>
            {p && (
              <>
                <div className="big num">{won(p.predicted_price)}원<span style={{ fontSize: 17 }}>/kg</span></div>
                <div className="small">
                  <PctChange value={p.change_pct} /> <span className="muted">오늘 {wonPerKg(p.base_price)} 대비 · 신뢰도 {p.confidence}</span>
                </div>
              </>
            )}
          </div>
          {options.data && (
            <div className="seg" role="group" aria-label="예측 기간">
              {options.data.horizons.map((x) => (
                <button key={x.days} className={h === x.days ? "on" : ""} onClick={() => setHorizon(x.days)}>{x.label}</button>
              ))}
              <Link className="seg-link" to={item ? `/ai?item=${item}&date=${addDays(todayIso(), h)}` : "/ai"}>📅 날짜</Link>
            </div>
          )}
        </div>
        <Async state={result} minHeight={260}>
          {(d) => (
            <>
              <ForecastChart p={d} height={250} legend={false} />
              {d.alerts[0] && (
                <p className="small" style={{ margin: "4px 0 0", color: "#9a6200" }}>
                  ⚠️ {md(d.alerts[0].start)}~{md(d.alerts[0].end)} 이상기후 주의 구간 — 이 기간 예측은 참고용으로 보세요
                </p>
              )}
            </>
          )}
        </Async>
        <div className="mini-movers">
          {(movers.data ?? []).map((m) => (
            <button key={m.item} className={`mini-mover ${item === m.item ? "on" : ""}`} onClick={() => setPicked(m.item)}>
              <span className="item-cell"><ItemImage code={m.item} emoji={info[m.item]?.emoji} className="xs" /> {m.item_name}</span>
              <PctChange value={m.change_pct} />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <div className="page">
      <NoticeBanner />
      {/* 예측을 가장 먼저, 오늘 시세는 그 아래에 */}
      <ForecastHero />
      <TodayPrices />
      <NewsHeadlines />
      <WeatherMap />
      <PopularAuctions />
    </div>
  );
}
