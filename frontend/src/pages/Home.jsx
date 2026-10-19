import { Link } from "react-router-dom";
import { getNotices } from "../api/admin";
import { getAuctions } from "../api/auction";
import { getItems, getTopMovers } from "../api/ml";
import { getTodayPrices, getWeather } from "../api/market";
import { Async, PctChange, PriceChange, SectionHead, useAsync } from "../components/common";
import { AuctionCard } from "./Auctions";
import { shortDate, wonPerKg } from "../utils/format";

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
    <section className="card">
      <Async state={state} minHeight={260}>
        {(d) => (
          <>
            <SectionHead
              title="오늘의 주요 시세"
              desc={`${shortDate(d.base_date)} · ${d.market} 도매가 기준 (1kg) · ${shortDate(d.compared_date)} 대비`}
              right={<Link className="link" to="/market">전체 시세 →</Link>}
            />
            <div className="grid grid-auto">
              {d.items.slice(0, HOME_PRICE_COUNT).map((p) => (
                <Link key={p.item} to={`/market?item=${p.item}`} className="price-card">
                  <span className="emoji">{p.emoji}</span>
                  <span className="muted small">{p.name}</span>
                  <span className="price num">{wonPerKg(p.price)}</span>
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

function Weather() {
  const state = useAsync(getWeather);
  return (
    <section className="card weather">
      <Async state={state}>
        {(w) => (
          <>
            <div className="small" style={{ opacity: 0.85 }}>🌦️ 실시간 농업 날씨 · {w.location}</div>
            <div className="temp">{w.temp}°</div>
            <div>{w.summary} · 최저 {w.min}° / 최고 {w.max}°</div>
            <div className="stats">
              <div>💧 습도 {w.humidity}%</div>
              <div>🌬️ 풍속 {w.wind}m/s</div>
              <div>🌡️ 지온 {w.soil_temp}°</div>
            </div>
            <div className="small" style={{ marginTop: 14, opacity: 0.85 }}>{w.note}</div>
          </>
        )}
      </Async>
    </section>
  );
}

function PopularAuctions() {
  const state = useAsync(() => getAuctions({ sort: "popular" }));
  return (
    <section>
      <SectionHead title="🔥 인기 경매" desc="지금 입찰이 몰리는 상품" right={<Link className="link" to="/auctions">전체 보기 →</Link>} />
      <Async state={state} empty="진행 중인 경매가 없습니다">
        {(rows) => (
          <div className="h-scroll">
            {rows.map((a) => <AuctionCard key={a.id} a={a} />)}
          </div>
        )}
      </Async>
    </section>
  );
}

function TopMovers() {
  const state = useAsync(async () => {
    const [movers, items] = await Promise.all([getTopMovers({ horizon: 7, limit: 4 }), getItems()]);
    const emoji = Object.fromEntries(items.map((i) => [i.code, i.emoji]));
    return movers.map((m) => ({ ...m, emoji: emoji[m.item] }));
  });
  return (
    <section>
      <SectionHead title="AI 추천 · 급등락 예상 품목" desc="향후 1주 예측 기준 · 전국" right={<Link className="link" to="/ai">예측 툴 →</Link>} />
      <Async state={state}>
        {(rows) => (
          <div className="grid grid-auto">
            {rows.map((m) => (
              <Link key={m.item} to={`/ai?item=${m.item}`} className="mover">
                <span className="small" style={{ color: "var(--green)" }}>✨ AI 신뢰도 {m.confidence}%</span>
                <b style={{ fontSize: 17 }}>{m.emoji} {m.item_name}</b>
                <PctChange value={m.change_pct} className="big" />
                <span className="muted small">1주 후 예상 {wonPerKg(m.predicted_price)}</span>
              </Link>
            ))}
          </div>
        )}
      </Async>
    </section>
  );
}

export default function Home() {
  return (
    <div className="page">
      <NoticeBanner />
      <div className="split">
        <TodayPrices />
        <Weather />
      </div>
      <PopularAuctions />
      <TopMovers />
    </div>
  );
}
