import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { predict, recommendCrops } from "../api/ml";
import { NEWS_CATEGORIES, getNews } from "../api/news";
import { getWeatherHistory, summarizeRegion } from "../api/weather";
import { useAuth } from "../components/AuthContext";
import { useAsync } from "../components/common";
import { SIDO, addDays, md, timeAgo, todayIso, won } from "../utils/format";
import "./home.css";

/* ─────────────────────────────────────────────
   홈 (v17, 11-11)
   첫 화면: 밭 사진 + 왼쪽 큰 메뉴(가격 예측 · 작물 추천) + 오른쪽 미리보기 카드 (마우스를 올리면 바뀜, 누르면 그 화면으로)
   스크롤: 첫 화면은 그대로 멈춰 있고(sticky) 아래 흰 화면이 올라와 덮음 → 오늘의 농업 정보(뉴스 · 날씨 나란히) → 서비스 소개
   ───────────────────────────────────────────── */

const MENU = [
  ["ai", "가격 예측", "언제 팔면 가장 비쌀까", "/ai"],
  ["rc", "작물 추천", "내 땅에 무엇을 심을까", "/recommend"],
];
// 가격 예측 카드에서 돌려 보여 줄 품목 (5초마다)
const AI_ITEMS = [
  ["napa_cabbage", "🥬", "배추"],
  ["onion", "🧅", "양파"],
  ["apple", "🍎", "사과"],
];
const LAND_TYPES = [["open", "노지"], ["house", "시설"], ["paddy", "논"], ["orchard", "과수원"]];

/** 일별 값 → 주 단위 (뒤에서부터 7일마다 하나) */
const weekly = (arr, n) => {
  const out = [];
  for (let i = arr.length - 1; i >= 0 && out.length < n; i -= 7) out.unshift(arr[i]);
  return out;
};

/** 0 에서 to 까지 세어 올라가는 숫자 */
function useCountUp(to, key) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (to == null) return undefined;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setV(to);
      return undefined;
    }
    let raf;
    const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / 900);
      setV(Math.round(to * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, key]);
  return v;
}

/** 가격 예측 미리보기: 지난 7주 + 앞으로 4주, 가장 비싼 주에 팔면 지금보다 얼마 더 받는지 크게 */
function AiPane({ on }) {
  const [idx, setIdx] = useState(0);
  const [hold, setHold] = useState(false);
  const [code, emoji, name] = AI_ITEMS[idx];
  const state = useAsync(() => predict({ item: code, horizon: 28, history_days: 49 }), [code]);
  // 5초마다 다음 품목 (마우스를 카드에 올리면 멈춤)
  useEffect(() => {
    if (!on || hold) return undefined;
    const t = setTimeout(() => setIdx((i) => (i + 1) % AI_ITEMS.length), 5000);
    return () => clearTimeout(t);
  }, [on, hold, idx]);

  const d = state.data;
  const past = d ? weekly(d.history, 8).map((p) => p.price) : [];
  const futW = d ? [7, 14, 21, 28].map((t) => d.forecast.find((f) => f.date === addDays(d.base_date, t))?.price ?? null) : []; // 날짜로 찾음 (DB 예측기는 예측 없는 날을 뺌, 11-11)
  const fut = futW.filter((v) => v != null);
  const now = d?.base_price ?? 0;
  const top = fut.length ? Math.max(...fut) : 0;
  const wk = futW.indexOf(top) + 1;
  const gain = top - now;
  const shown = useCountUp(d ? gain : null, `${code}-${on}`);

  // 그래프 좌표
  const W = 600, H = 230;
  const all = [...past, ...fut];
  const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo || 1) * 0.35;
  const X = (j) => 22 + (j * (W - 44)) / Math.max(1, all.length - 1);
  const Y = (v) => 30 + ((hi + pad - v) / (hi - lo + pad * 2 || 1)) * (H - 62);
  const k = past.length - 1;
  const fu = [now, ...fut];
  const bi = past.length + fut.indexOf(top);
  const p1 = past.map((v, j) => `${X(j)},${Y(v)}`).join(" ");
  const p2 = fu.map((v, j) => `${X(k + j)},${Y(v)}`).join(" ");
  const flagW = 120;

  return (
    <div className={`hv-pane ${on ? "on" : ""}`} onMouseEnter={() => setHold(true)} onMouseLeave={() => setHold(false)}>
      <div className="hv-ai-top">
        <span className="hv-tag">AI 가격 예측 <i className="hv-live" /> 매일 06:00 갱신</span>
        <div className="hv-ai-items">
          {AI_ITEMS.map(([c, , n], j) => (
            <button key={c} type="button" className={j === idx ? "on" : ""} onClick={() => setIdx(j)}>{n}</button>
          ))}
        </div>
      </div>
      <div className="hv-ai-name"><span>{emoji}</span>{name} · {d?.market_name === "전국 평균" ? "전국 도매시장" : d?.market_name ?? ""} <small>원/kg</small></div>
      {d && fut.length > 0 && (
        <>
          <div className="hv-ai-hero" key={code}>
            <div className="hv-gain">
              <small>{gain > 0 ? `${wk}주 뒤에 팔면 지금보다 kg당` : "앞으로 4주 동안 지금보다"}</small>
              <b>{gain > 0 ? `+${won(shown)}원` : "낮아요"}</b>
            </div>
            <div className="hv-ai-sub">
              지금 <b>{won(now)}원</b> → {wk}주 뒤 <b className="hi">{won(top)}원</b> 예상
              {gain > 0 && <span className="hv-pill-up">▲ {((gain / now) * 100).toFixed(1)}%</span>}
            </div>
          </div>
          <svg className="hv-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={`${name} 지난 7주와 앞으로 4주 예상 가격`}>
            <defs>
              <linearGradient id="hvAmber" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#f0a52a" stopOpacity=".38" /><stop offset="1" stopColor="#f0a52a" stopOpacity="0" /></linearGradient>
              <linearGradient id="hvGreen" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#3c8a5c" stopOpacity=".16" /><stop offset="1" stopColor="#3c8a5c" stopOpacity="0" /></linearGradient>
              <filter id="hvGlow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
            </defs>
            <polygon points={`${X(0)},${H - 30} ${p1} ${X(k)},${H - 30}`} fill="url(#hvGreen)" />
            <polygon points={`${X(k)},${H - 30} ${p2} ${X(all.length - 1)},${H - 30}`} fill="url(#hvAmber)" />
            <line x1={X(k)} x2={X(k)} y1="14" y2={H - 30} stroke="rgba(19,38,26,.28)" strokeDasharray="4 4" />
            <text x={X(k)} y={H - 8} textAnchor="middle" fontSize="16" fontWeight="700" fill="#13261a">지금</text>
            <text x={X(0)} y={H - 8} fontSize="15" fill="rgba(19,38,26,.8)">7주 전</text>
            <text x={X(all.length - 1)} y={H - 8} textAnchor="end" fontSize="15" fill="rgba(19,38,26,.8)">4주 뒤</text>
            <polyline className="hv-path" points={p1} fill="none" stroke="rgba(19,38,26,.55)" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
            <polyline className="hv-path" points={p2} fill="none" stroke="#e8890c" strokeWidth="5" strokeLinejoin="round" strokeLinecap="round" filter="url(#hvGlow)" />
            <circle cx={X(k)} cy={Y(now)} r="5.5" fill="#13261a" stroke="#fff" strokeWidth="2" />
            <circle className="hv-pin" cx={X(bi)} cy={Y(top)} r="10" fill="none" stroke="#d92d20" strokeWidth="2.5" />
            <circle cx={X(bi)} cy={Y(top)} r="8" fill="#d92d20" stroke="#fff" strokeWidth="3" />
            <g className="hv-flag">
              <rect x={Math.min(X(bi) - flagW / 2, W - flagW - 4)} y={Y(top) - 46} width={flagW} height="30" rx="15" fill="#d92d20" />
              <text x={Math.min(X(bi), W - flagW / 2 - 4)} y={Y(top) - 26} textAnchor="middle" fontSize="16" fontWeight="800" fill="#fff">최고 {won(top)}원</text>
            </g>
          </svg>
          <div className="hv-ai-foot"><span className="hv-acc">최근 정확도 {d.confidence}%</span></div>
        </>
      )}
      {state.loading && !d && <div className="hv-wait">예측 불러오는 중…</div>}
    </div>
  );
}

/** 작물 추천 미리보기: 내 지역 · 고른 땅 · 오늘 심으면 순수익 TOP3 */
function CropPane({ on }) {
  const { user } = useAuth();
  const [type, setType] = useState("open");
  const region = user?.region || "경기";
  const state = useAsync(
    () => recommendCrops({ region, lands: [{ type, area_pyeong: 1200 }], start_date: todayIso() }),
    [region, type],
  );
  const rows = (state.data?.results ?? []).slice(0, 3);
  const max = Math.max(1, ...rows.map((r) => r.margin));
  return (
    <div className={`hv-pane ${on ? "on" : ""}`}>
      <span className="hv-tag">작물 추천</span>
      <h3>지금 심기 좋은 작물 <small>{region} · {LAND_TYPES.find(([k]) => k === type)[1]} · 1,200평</small></h3>
      <div className="hv-chips">
        {LAND_TYPES.map(([k, label]) => (
          <button key={k} type="button" className={k === type ? "on" : ""} onClick={() => setType(k)}>{label}</button>
        ))}
      </div>
      <ul className="hv-crops">
        {rows.map((r, i) => (
          <li key={r.crop}>
            <span className="n">{String(i + 1).padStart(2, "0")}</span>
            <span className="nm">{r.crop_name}<small>{r.cropping} · {Number(r.harvest_start.slice(5, 7))}월 수확</small></span>
            <span className="v">{won(Math.round(r.margin / 10000))}만원<small>예상 순수익 · 마진 {Math.round(r.margin_rate)}%</small></span>
            <span className="bar"><i style={{ width: on ? `${(r.margin / max) * 100}%` : 0 }} /></span>
          </li>
        ))}
      </ul>
      {state.data && !rows.length && <p className="hv-wait">오늘 이 땅에 심을 수 있는 작물이 없어요. 다른 땅을 골라 보세요.</p>}
      {state.loading && !state.data && <div className="hv-wait">추천 불러오는 중…</div>}
    </div>
  );
}

function Hero() {
  const [k, setK] = useState("ai");
  const nav = useNavigate();
  return (
    <section className="hv-hero">
      <div className="hv-bg" aria-hidden><i /></div>
      <div className="hv-stage">
        <section className="hv-left">
          <p className="hv-lead">공영도매시장 <b>32곳</b> · <b>50</b>개 품목 · AI가 알려 주는 농사 정보</p>
          <ul className="hv-menu">
            {MENU.map(([key, t, s, to]) => (
              <li key={key} className={k === key ? "on" : ""} onMouseEnter={() => setK(key)}>
                {/* 마우스: 올리면 미리보기, 누르면 이동 · 터치: 처음 누르면 미리보기, 한 번 더 누르면 이동 */}
                <button
                  type="button"
                  onFocus={() => setK(key)}
                  onClick={() => {
                    const hover = window.matchMedia?.("(hover: hover)").matches;
                    if (hover || k === key) nav(to);
                    else setK(key);
                  }}
                >
                  <span className="t">{t}</span>
                  <span className="s">{s}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <section className="hv-preview" aria-live="polite">
          <AiPane on={k === "ai"} />
          <CropPane on={k === "rc"} />
        </section>
      </div>
      <a className="hv-cue" href="#today">오늘의 뉴스 · 날씨<i aria-hidden>↓</i></a>
    </section>
  );
}

function NewsCard() {
  const [cat, setCat] = useState("");
  const state = useAsync(() => getNews({ category: cat, size: 6 }), [cat]);
  return (
    <article className="hv-card">
      <div className="hv-card-head"><h3>📰 농업 뉴스</h3><Link to="/news">뉴스 더 보기 ›</Link></div>
      <div className="hv-tabs">
        {["", ...NEWS_CATEGORIES].map((c) => (
          <button key={c || "all"} type="button" className={c === cat ? "on" : ""} onClick={() => setCat(c)}>{c || "전체"}</button>
        ))}
      </div>
      <ul className="hv-nlist">
        {(state.data?.rows ?? []).map((n) => (
          <li key={n.id}>
            <span className="c">{n.category}</span>
            <a className="tt" href={n.url} target="_blank" rel="noreferrer">{n.title}</a>
            <span className="p">{n.press} · {timeAgo(n.published_at)}</span>
          </li>
        ))}
      </ul>
      {state.data && !state.data.rows.length && <p className="hv-wait">이 분류의 오늘 뉴스가 아직 없어요.</p>}
    </article>
  );
}

/* 날씨 카드 (11-11): 서버 날씨 수집기가 만든 시·도 일별 관측(/data/weather/regions-daily.json)으로 어제 날씨 + 최근 7일 평년 대비·주의 신호.
   서버 연결이 없는 개발 화면은 예시 데이터 (출처 줄에 "예시 데이터"). 예보가 아니라 관측이라 "어제" 기준 */
const nz = (v, unit = "") => (v == null ? "–" : `${v}${unit}`);
const skyOf = (d) => {
  if ((d.rain_mm ?? 0) >= 1) return d.temp_max != null && d.temp_max <= 1 ? ["🌨️", "눈·비"] : ["🌧️", "비"];
  if (d.sun_hours == null) return ["🌤️", ""];
  return d.sun_hours >= 6 ? ["☀️", "맑음"] : d.sun_hours >= 2 ? ["⛅", "구름 조금"] : ["☁️", "흐림"];
};
function weekLine(s) {
  const w = s.week_vs_normal;
  if (!w) return `최근 7일 비 ${s.week_rain}mm`;
  const t = Math.abs(w.temp_diff) < 0.5 ? "평년과 비슷했고" : `평년보다 ${Math.abs(w.temp_diff)}° ${w.temp_diff > 0 ? "따뜻했고" : "추웠고"}`;
  return `최근 7일은 ${t}, 비는 ${w.rain}mm 왔어요 (평년 ${w.normal_rain}mm)`;
}

function WeatherCard() {
  const { user } = useAuth();
  const state = useAsync(getWeatherHistory);
  const [pick, setPick] = useState("");
  const h = state.data;
  const regions = h ? SIDO.filter((r) => h.daily.regions?.[r]?.length) : [];
  const name = regions.includes(pick) ? pick : regions.includes(user?.region) ? user.region : regions.includes("경기") ? "경기" : regions[0];
  const s = h && name ? summarizeRegion(h, name) : null;
  const d = s?.last;
  const lastOf = (r) => h.daily.regions[r].at(-1);
  const others = regions.filter((r) => r !== name).slice(0, 8);
  const [icon, sky] = d ? skyOf(d) : [];
  const sig = s?.signals[0];
  return (
    <article className="hv-card">
      <div className="hv-card-head">
        <h3>🌤️ 우리 지역 농업 날씨</h3>
        {regions.length > 0 && (
          <select className="hv-sel" value={name} onChange={(e) => setPick(e.target.value)} aria-label="지역">
            {regions.map((r) => <option key={r}>{r}</option>)}
          </select>
        )}
      </div>
      {state.error && <p className="hv-wait">날씨 자료를 아직 받지 못했어요. 잠시 뒤 다시 확인해 주세요.</p>}
      {h && !d && <p className="hv-wait">날씨 자료가 아직 없어요.</p>}
      {d && (
        <>
          <div className="hv-wx-now"><span className="ic" aria-hidden>{icon}</span><div><b>{nz(d.temp_avg, "°")}</b><p>어제({md(d.date)}) 평균{sky ? ` · ${sky}` : ""} · 최저 {nz(d.temp_min, "°")} / 최고 {nz(d.temp_max, "°")}</p></div></div>
          <div className="hv-wx-facts">
            <span>☔ 강수량<b>{nz(d.rain_mm, "mm")}</b></span><span>💧 습도<b>{nz(d.humidity, "%")}</b></span>
            <span>🍃 순간풍속<b>{nz(d.gust, "m/s")}</b></span><span>☀️ 일조<b>{nz(d.sun_hours, "시간")}</b></span>
          </div>
          {sig ? <p className="hv-warn">⚠️ {name} 최근 7일 {sig.text} — {sig.tip}</p> : <p className="hv-note">🌱 {weekLine(s)}</p>}
          <div className="hv-wx-grid">
            {others.map((r) => <button key={r} type="button" onClick={() => setPick(r)}>{skyOf(lastOf(r))[0]} {r}<b>{nz(lastOf(r).temp_avg, "°")}</b></button>)}
          </div>
        </>
      )}
      <p className="hv-src">기상청 관측{d ? ` · ${md(d.date)}까지` : ""}{s?.stale_days > 0 ? ` (${s.stale_days}일 늦음)` : ""}{h?.sample ? " · 예시 데이터" : ""}</p>
    </article>
  );
}

const INTRO = [
  ["📈", "AI 가격 예측", [["언제 팔까", "/ai"], ["품목 50개", "/about#items"], ["예측 기간", "/about#faq-range"], ["오차 범위", "/about#faq-accuracy"]]],
  ["🌱", "작물 추천", [["내 땅 넣기", "/recommend"], ["순수익 순위", "/recommend"], ["재배 달력", "/recommend?tab=info"], ["작물 정보", "/recommend?tab=info"]]],
  // 자주 묻는 질문은 서비스 소개 페이지의 "자주 묻는 질문"(#faq)으로, 누르면 그 질문이 펼쳐짐 (11-13)
  ["❓", "자주 묻는 질문", [["가격 기준", "/about#faq-price"], ["등급 기준", "/about#faq-grade"], ["예측 정확도", "/about#faq-accuracy"], ["자료 출처", "/about#faq-source"], ["전체 질문 보기", "/about#faq"]]],
  ["✉️", "문의하기", [["contact@nongclock.kr", "/about#contact"], ["02-000-0000", "/about#contact"], ["평일 10:00~18:00", "/about#contact"]]],
];

export default function Home() {
  // 스크롤을 내리기 시작하면 "오늘의 뉴스 · 날씨" 안내는 사라짐
  const root = useRef(null);
  useEffect(() => {
    const on = () => {
      const el = root.current?.querySelector(".hv-cue");
      if (el) el.style.opacity = String(Math.max(0, 1 - window.scrollY / 160));
    };
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <div className="hv" ref={root}>
      <Hero />
      <section className="hv-today" id="today">
        <div className="hv-wrap">
          <div className="hv-sec-head"><h2>오늘의 농업 정보</h2><span>{todayIso().replaceAll("-", ". ")}. · 뉴스 1시간마다 · 날씨 3시간마다 갱신</span></div>
          <div className="hv-two">
            <NewsCard />
            <WeatherCard />
          </div>
        </div>
      </section>
      <section className="hv-intro" id="intro">
        <div className="hv-wrap">
          <div className="hv-sec-head"><h2>서비스 소개</h2><span>NongClock은 AI 가격 예측으로 농가의 판단을 돕는 서비스예요. 예측은 참고용이고, 실제 가격은 수급·유통 상황에 따라 달라질 수 있어요.</span></div>
          <div className="hv-ig">
            {INTRO.map(([e, t, ls]) => (
              <div key={t} className="hv-ic-card">
                <h4><span aria-hidden>{e}</span>{t}</h4>
                <ul>{ls.map(([l, to]) => <li key={l}><Link to={to}>{l}</Link></li>)}</ul>
              </div>
            ))}
          </div>
          <Link className="hv-team" to="/about#team">› 만든 사람들 <span>농산물 가격 예측 플랫폼 팀 프로젝트 · 2026</span></Link>
        </div>
      </section>
    </div>
  );
}
