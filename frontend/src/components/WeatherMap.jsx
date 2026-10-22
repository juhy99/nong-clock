import { useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import southKorea from "@svg-maps/south-korea";
import { getMarkets, getRegionalWeather } from "../api/market";
import { useAuth } from "./AuthContext";
import { Async, useAsync } from "./common";
import { dateTime } from "../utils/format";

// 지도 위에 이름·기온을 항상 표시할 지역 (광역시처럼 작은 곳은 겹쳐서 고를 때만 표시)
const LABELED = new Set(["gyeonggi", "gangwon", "north-chungcheong", "south-chungcheong", "north-jeolla", "south-jeolla", "north-gyeongsang", "south-gyeongsang", "jeju"]);

// 위도·경도 → 지도(viewBox 0 0 524 631) 좌표. 광역시 7곳 중심으로 맞춘 근사식 (오차 몇 px)
const toMap = (lat, lon) => [92.733 * lon - 11623.09, -114.217 * lat + 4424.165];
// 시·도 경계에 붙어 있어 옆 지역에 찍히는 시장만 자기 지역 안쪽으로 몇 px 옮긴다
const NUDGE = { 110001: [-1, -5], 230001: [-3, -5], 311201: [6, 1] };
const marketPoint = (m) => {
  const [x, y] = toMap(m.lat, m.lon);
  const [dx, dy] = NUDGE[m.code] ?? [0, 0];
  return [x + dx, y + dy];
};

/** 값이 없으면(테스트 모드에서 기상청 결측) "—" */
const val = (v, unit = "") => (v == null ? "—" : `${v}${unit}`);

/** 기온 → 지도 색 (낮으면 파랑, 높으면 주황) */
function tempColor(t) {
  if (t == null) return "#eee";
  const x = Math.min(1, Math.max(0, (t - 4) / 18));
  const cold = [205, 225, 247];
  const warm = [250, 196, 140];
  const mix = cold.map((c, i) => Math.round(c + (warm[i] - c) * x));
  return `rgb(${mix.join(",")})`;
}

const FULL = [0, 0, 524, 631];
/** 고른 지역을 화면 비율(524:631)에 맞춰 넉넉히 감싸는 viewBox */
function zoomBox(b) {
  if (!b) return FULL;
  let w = Math.max(b.w * 1.5, 150), h = Math.max(b.h * 1.5, 150);
  if (w / h > 524 / 631) h = (w * 631) / 524;
  else w = (h * 524) / 631;
  return [b.x + b.w / 2 - w / 2, b.y + b.h / 2 - h / 2, w, h];
}

function KoreaMap({ regions, markets, selected, zoom, onSelect, onMeasure }) {
  const refs = useRef({});
  const [boxes, setBoxes] = useState({});
  useLayoutEffect(() => {
    const c = {};
    for (const [id, el] of Object.entries(refs.current)) {
      const b = el.getBBox();
      c[id] = { x: b.x, y: b.y, w: b.width, h: b.height, cx: b.x + b.width / 2, cy: b.y + b.height / 2 };
    }
    setBoxes(c);
    onMeasure?.(c);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const byId = Object.fromEntries(regions.map((r) => [r.id, r]));
  const regionOf = Object.fromEntries(regions.map((r) => [r.name, r.id]));
  // 확대하면 글자·점 크기가 그대로 보이도록 k(축척)를 곱한다
  const vb = zoom ? zoomBox(boxes[selected]) : FULL;
  const k = vb[2] / 524;

  return (
    <svg viewBox={vb.join(" ")} className={`korea-map ${zoom ? "zoomed" : ""}`} role="group" aria-label="지역을 눌러 날씨와 도매시장 보기">
      {southKorea.locations.map((loc) => {
        const r = byId[loc.id];
        return (
          <path
            key={loc.id}
            ref={(el) => el && (refs.current[loc.id] = el)}
            d={loc.path}
            fill={tempColor(r?.temp)}
            vectorEffect="non-scaling-stroke"
            className={`region ${selected === loc.id ? "on" : ""} ${r?.warning ? "warn" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={`${r?.name} ${val(r?.temp, "도")}`}
            aria-pressed={selected === loc.id}
            onClick={() => onSelect(loc.id)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect(loc.id))}
          />
        );
      })}
      {Object.entries(boxes).map(([id, b]) =>
        (zoom ? id === selected : LABELED.has(id) || id === selected) ? (
          <text key={id} x={b.cx} y={b.cy} className={`map-label ${id === selected ? "on" : ""}`} textAnchor="middle"
            style={{ fontSize: (id === selected ? 15 : 13) * k, strokeWidth: 3 * k }}>
            <tspan x={b.cx} dy="-0.2em">{byId[id]?.name}</tspan>
            <tspan x={b.cx} dy="1.15em" className="t">{val(byId[id]?.temp, "°")}</tspan>
          </text>
        ) : null,
      )}
      {markets.map((m) => {
        const [x, y] = marketPoint(m);
        const on = regionOf[m.sido] === selected;
        return (
          <g key={m.code} className={`mkt ${on ? "on" : ""}`} onClick={() => onSelect(regionOf[m.sido])}>
            <title>{`${m.name} 도매시장 (${m.sido} ${m.sigungu})`}</title>
            <circle cx={x} cy={y} r={(on ? 5.5 : 3.8) * k} style={{ strokeWidth: 1.6 * k }} />
            {zoom && on && <text x={x + 8 * k} y={y + 4 * k} className="mkt-label" style={{ fontSize: 12 * k, strokeWidth: 3 * k }}>{m.name}</text>}
          </g>
        );
      })}
    </svg>
  );
}

/** 시장 시세 화면 주소: 관심 품목 중 그 시장에서 거래하는 첫 품목, 없으면 그 시장 물량 1위 품목 */
function marketLink(m, favorites = []) {
  const item = favorites.find((f) => m.items?.includes(f)) ?? m.top_item;
  return `/market?market=${m.code}${item ? `&item=${item}` : ""}`;
}

/** 고른 지역의 공영 도매시장. 없으면 지도에서 가장 가까운 시장 2곳 */
function RegionMarkets({ region, markets, center, favorites }) {
  const here = markets.filter((m) => m.sido === region.name);
  if (here.length) {
    return (
      <div className="region-markets">
        <div className="rm-head"><b>{region.name} 도매시장</b><span className="muted small">{here.length}곳</span></div>
        <ul>
          {here.map((m) => (
            <li key={m.code}>
              <span className="dot" />
              <b>{m.name}</b>
              <span className="muted small">{m.sigungu}</span>
              <Link className="go small" to={marketLink(m, favorites)}>시세 보기 ›</Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  const near = center
    ? [...markets].sort((a, b) => {
        const d = (m) => { const [x, y] = marketPoint(m); return (x - center.cx) ** 2 + (y - center.cy) ** 2; };
        return d(a) - d(b);
      }).slice(0, 2)
    : [];
  return (
    <div className="region-markets">
      <div className="rm-head"><b>{region.name} 도매시장</b><span className="muted small">없음</span></div>
      <p className="small muted" style={{ margin: 0 }}>
        {region.name}에는 공영 도매시장이 없어요.
        {near.length > 0 && <> 가까운 시장: {near.map((m, i) => <span key={m.code}>{i > 0 && " · "}<Link className="link" to={marketLink(m, favorites)}>{m.name}</Link></span>)}</>}
      </p>
    </div>
  );
}

/** 홈: 지도에서 시·도를 누르면 그 지역 농업 날씨와 공영 도매시장을 보여준다 */
export default function WeatherMap() {
  const { user } = useAuth();
  const state = useAsync(getRegionalWeather);
  const marketState = useAsync(getMarkets);
  const markets = (marketState.data ?? []).filter((m) => m.lat != null);
  const [picked, setPicked] = useState(null);
  const [zoom, setZoom] = useState(false);
  const [boxes, setBoxes] = useState({});
  // 지도·목록에서 지역을 고르면 그 지역으로 확대한다
  const pick = (id) => { setPicked(id); setZoom(true); };

  return (
    <section className="card weather-map">
      <Async state={state} minHeight={420}>
        {(w) => {
          // 처음에는 회원 지역(없으면 경기)
          const mine = w.regions.find((r) => r.name === user?.region)?.id ?? "gyeonggi";
          const sel = w.regions.find((r) => r.id === (picked ?? mine));
          const warnings = w.regions.filter((r) => r.warning);
          return (
            <div className="weather-grid">
              <div className="map-wrap">
                <KoreaMap regions={w.regions} markets={markets} selected={sel.id} zoom={zoom} onSelect={pick} onMeasure={setBoxes} />
                {zoom && <button type="button" className="btn sm map-reset" onClick={() => setZoom(false)}>전국 지도</button>}
                <div className="map-legend small">
                  <span>추움</span><i /><span>따뜻함</span>
                  <span className="mkt-key">공영 도매시장 {markets.length}곳</span>
                </div>
              </div>
              <div className="weather-detail">
                <div className="card-head" style={{ marginBottom: 8 }}>
                  <div>
                    <h2>우리 지역 농업 날씨</h2>
                    <p>지도에서 지역을 눌러 보세요 · 초록 점은 도매시장 · {dateTime(w.base_time)} 발표</p>
                  </div>
                </div>
                <select className="input" aria-label="지역 선택" value={sel.id} onChange={(e) => pick(e.target.value)} style={{ maxWidth: 200 }}>
                  {w.regions.map((r) => <option key={r.id} value={r.id}>{r.name}{r.warning ? " ⚠️" : ""}</option>)}
                </select>
                <div className="weather-now">
                  <div className="big-icon">{sel.icon}</div>
                  <div>
                    <div className="muted small">{sel.name}</div>
                    <div className="temp">{val(sel.temp, "°")}</div>
                    <div>{sel.sky} · 최저 {val(sel.min, "°")} / 최고 {val(sel.max, "°")}</div>
                  </div>
                </div>
                {sel.warning && <span className="warn-chip">⚠️ {sel.name} {sel.warning}</span>}
                <div className="stats">
                  <div>☔ 강수확률 {val(sel.rain_prob, "%")}</div>
                  <div>💧 습도 {val(sel.humidity, "%")}</div>
                  <div>🌬️ 풍속 {val(sel.wind, "m/s")}</div>
                  <div>🌡️ 지온 {val(sel.soil_temp, "°")}</div>
                </div>
                <p className="small" style={{ margin: 0 }}>🌱 {sel.note}</p>
                {markets.length > 0 && <RegionMarkets region={sel} markets={markets} center={boxes[sel.id]} favorites={user?.favorites} />}
                {warnings.length > 0 && (
                  <p className="small muted" style={{ margin: 0 }}>
                    전국 특보: {warnings.map((r) => `${r.name} ${r.warning}`).join(" · ")}
                  </p>
                )}
                <p className="map-credit">지도: svg-maps/south-korea (CC BY 4.0)</p>
              </div>
            </div>
          );
        }}
      </Async>
    </section>
  );
}
