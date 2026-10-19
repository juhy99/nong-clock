import { useState } from "react";
import { Link } from "react-router-dom";
import { getNotices } from "../api/admin";
import { getAuctions } from "../api/auction";
import { getHorizons, getItems, getTopMovers, predict } from "../api/ml";
import { getTodayPrices, getWeather } from "../api/market";
import { Async, PriceChange, SectionHead, useAsync } from "../components/common";
import ForecastChart from "../components/ForecastChart";
import { AuctionCard } from "./Auctions";
import { md, shortDate, wonPerKg } from "../utils/format";

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

/** 홈 맨 위: AI 예측으로 본 앞으로의 가격 (품목·기간을 바꿔 가며 바로 확인) */
function ForecastHero() {
  const options = useAsync(async () => {
    const [items, horizons] = await Promise.all([getItems(), getHorizons()]);
    return { items, horizons };
  });
  const [horizon, setHorizon] = useState(null);
  const [picked, setPicked] = useState(null);
  const h = horizon ?? options.data?.horizons[0]?.days;
  const hLabel = options.data?.horizons.find((x) => x.days === h)?.label ?? "";
  const emoji = Object.fromEntries((options.data?.items ?? []).map((i) => [i.code, i.emoji]));

  const movers = useAsync(() => (h ? getTopMovers({ horizon: h, limit: 4 }) : Promise.resolve(null)), [h]);
  // 품목을 고르지 않았으면 가장 크게 움직일 품목을 먼저 보여준다
  const item = picked ?? movers.data?.[0]?.item;
  const result = useAsync(() => (item && h ? predict({ item, horizon: h }) : Promise.resolve(null)), [item, h]);
  const p = result.data;

  return (
    <section className="card hero">
      <div className="card-head" style={{ marginBottom: 12 }}>
        <div>
          <h2>🤖 AI가 예측한 앞으로의 가격</h2>
          <p>{p ? `${shortDate(p.base_date)} 기준 · ` : ""}전국 도매가(원/kg) · 매일 갱신</p>
        </div>
        {options.data && (
          <div className="pills">
            {options.data.horizons.map((x) => (
              <button key={x.days} className={`pill ${h === x.days ? "on" : ""}`} onClick={() => setHorizon(x.days)}>
                {x.label}
              </button>
            ))}
          </div>
        )}
      </div>
      {options.data && (
        <div className="pills scroll-row">
          {options.data.items.map((i) => (
            <button key={i.code} className={`pill ${item === i.code ? "on" : ""}`} onClick={() => setPicked(i.code)}>
              {i.emoji} {i.name}
            </button>
          ))}
        </div>
      )}
      <div className="hero-grid">
        <div className="hero-chart">
          <Async state={result} minHeight={300}>
            {(d) => (
              <>
                <ForecastChart p={d} height={300} />
                {d.alerts[0] && (
                  <p className="small" style={{ margin: "6px 0 0", color: "#9a6200" }}>
                    ⚠️ {md(d.alerts[0].start)}~{md(d.alerts[0].end)} 이상기후 주의 구간 — 이 기간 예측은 참고용으로 보세요
                  </p>
                )}
              </>
            )}
          </Async>
        </div>
        <div className="hero-side">
          {p && (
            <div className="hero-kpi">
              <div className="small hero-dim">{emoji[p.item]} {p.item_name} · {hLabel} 후 예상</div>
              <div className="big num">{wonPerKg(p.predicted_price)}</div>
              <div className="small">
                <b className={p.change_pct >= 0 ? "hero-up" : "hero-down"}>{p.change_pct > 0 ? "▲" : p.change_pct < 0 ? "▼" : "-"} {Math.abs(p.change_pct).toFixed(1)}%</b>{" "}
                <span className="hero-dim">오늘 {wonPerKg(p.base_price)} 대비 · 신뢰도 {p.confidence}</span>
              </div>
            </div>
          )}
          <div className="small hero-dim" style={{ marginTop: 4 }}>📈 {hLabel} 뒤 많이 움직일 품목</div>
          <Async state={movers}>
            {(rows) =>
              rows.map((m) => (
                <button key={m.item} className={`mini-mover ${item === m.item ? "on" : ""}`} onClick={() => setPicked(m.item)}>
                  <span>{emoji[m.item]} {m.item_name}</span>
                  <b className={m.change_pct >= 0 ? "hero-up" : "hero-down"}>
                    {m.change_pct > 0 ? "▲" : m.change_pct < 0 ? "▼" : "-"} {Math.abs(m.change_pct).toFixed(1)}%
                  </b>
                </button>
              ))
            }
          </Async>
          <Link className="btn hero-btn" to={item ? `/ai?item=${item}` : "/ai"}>자세한 예측 보기 →</Link>
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
      <div className="split">
        <TodayPrices />
        <Weather />
      </div>
      <PopularAuctions />
    </div>
  );
}
