import { useLayoutEffect, useRef, useState } from "react";
import southKorea from "@svg-maps/south-korea";
import { getRegionalWeather } from "../api/market";
import { useAuth } from "./AuthContext";
import { Async, useAsync } from "./common";
import { dateTime } from "../utils/format";

// 지도 위에 이름·기온을 항상 표시할 지역 (광역시처럼 작은 곳은 겹쳐서 고를 때만 표시)
const LABELED = new Set(["gyeonggi", "gangwon", "north-chungcheong", "south-chungcheong", "north-jeolla", "south-jeolla", "north-gyeongsang", "south-gyeongsang", "jeju"]);

/** 기온 → 지도 색 (낮으면 파랑, 높으면 주황) */
function tempColor(t) {
  const x = Math.min(1, Math.max(0, (t - 4) / 18));
  const cold = [205, 225, 247];
  const warm = [250, 196, 140];
  const mix = cold.map((c, i) => Math.round(c + (warm[i] - c) * x));
  return `rgb(${mix.join(",")})`;
}

function KoreaMap({ regions, selected, onSelect }) {
  const refs = useRef({});
  const [centers, setCenters] = useState({});
  useLayoutEffect(() => {
    const c = {};
    for (const [id, el] of Object.entries(refs.current)) {
      const b = el.getBBox();
      c[id] = [b.x + b.width / 2, b.y + b.height / 2];
    }
    setCenters(c);
  }, []);
  const byId = Object.fromEntries(regions.map((r) => [r.id, r]));

  return (
    <svg viewBox={southKorea.viewBox} className="korea-map" role="group" aria-label="지역을 눌러 날씨 보기">
      {southKorea.locations.map((loc) => {
        const r = byId[loc.id];
        return (
          <path
            key={loc.id}
            ref={(el) => el && (refs.current[loc.id] = el)}
            d={loc.path}
            fill={r ? tempColor(r.temp) : "#eee"}
            className={`region ${selected === loc.id ? "on" : ""} ${r?.warning ? "warn" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={`${r?.name} ${r?.temp}도`}
            aria-pressed={selected === loc.id}
            onClick={() => onSelect(loc.id)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelect(loc.id))}
          />
        );
      })}
      {Object.entries(centers).map(([id, [x, y]]) =>
        LABELED.has(id) || id === selected ? (
          <text key={id} x={x} y={y} className={`map-label ${id === selected ? "on" : ""}`} textAnchor="middle">
            <tspan x={x} dy="-0.2em">{byId[id]?.name}</tspan>
            <tspan x={x} dy="1.15em" className="t">{byId[id]?.temp}°</tspan>
          </text>
        ) : null,
      )}
    </svg>
  );
}

/** 홈: 지도에서 시·도를 누르면 그 지역 농업 날씨를 보여준다 */
export default function WeatherMap() {
  const { user } = useAuth();
  const state = useAsync(getRegionalWeather);
  const [picked, setPicked] = useState(null);

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
                <KoreaMap regions={w.regions} selected={sel.id} onSelect={setPicked} />
                <div className="map-legend small">
                  <span>추움</span><i /><span>따뜻함</span>
                </div>
              </div>
              <div className="weather-detail">
                <div className="card-head" style={{ marginBottom: 8 }}>
                  <div>
                    <h2>🌦️ 실시간 농업 날씨</h2>
                    <p>지도에서 지역을 눌러 보세요 · {dateTime(w.base_time)} 발표</p>
                  </div>
                </div>
                <select className="input" aria-label="지역 선택" value={sel.id} onChange={(e) => setPicked(e.target.value)} style={{ maxWidth: 200 }}>
                  {w.regions.map((r) => <option key={r.id} value={r.id}>{r.name}{r.warning ? " ⚠️" : ""}</option>)}
                </select>
                <div className="weather-now">
                  <div className="big-icon">{sel.icon}</div>
                  <div>
                    <div className="muted small">{sel.name}</div>
                    <div className="temp">{sel.temp}°</div>
                    <div>{sel.sky} · 최저 {sel.min}° / 최고 {sel.max}°</div>
                  </div>
                </div>
                {sel.warning && <div className="banner small">⚠️ <b>{sel.name} {sel.warning}</b></div>}
                <div className="stats">
                  <div>☔ 강수확률 {sel.rain_prob}%</div>
                  <div>💧 습도 {sel.humidity}%</div>
                  <div>🌬️ 풍속 {sel.wind}m/s</div>
                  <div>🌡️ 지온 {sel.soil_temp}°</div>
                </div>
                <p className="small" style={{ margin: 0 }}>🌱 {sel.note}</p>
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
