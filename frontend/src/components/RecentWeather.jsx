import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { summarizeRegion } from "../api/weather";
import { md } from "../utils/format";

const HI = "#e8710a"; // 최고기온
const LO = "#1a73e8"; // 최저기온
const RAIN = "#7fa7d9";
const t = (v) => (v == null ? "—" : `${v}°`);
const monthName = (ym) => `${Number(ym.slice(5, 7))}월`;
const signed = (n) => `${n > 0 ? "+" : ""}${n}`;
const tone = (d) => (d > 0 ? "rw-warm" : d < 0 ? "rw-cool" : "");

function TempTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rw-tip">
      <b>{md(d.date)}</b>
      <div><i style={{ background: HI }} />최고 {t(d.temp_max)}</div>
      <div><i style={{ background: LO }} />최저 {t(d.temp_min)}</div>
      <div><i style={{ background: RAIN }} />비 {d.rain_mm == null ? "—" : `${d.rain_mm}mm`}</div>
    </div>
  );
}

/** 홈 날씨 지도: 고른 시·도의 지난 날씨(관측). 데이터는 api/weather.js (서버의 날씨_대통합.csv) */
export default function RecentWeather({ state, sido }) {
  // 지난 날씨는 덤이라, 서버 파일이 없거나 오류면 조용히 숨긴다 (관리자 › 데이터 수집에서 확인)
  if (state.error || !state.data) return state.loading ? <div className="recent-weather muted small">지난 날씨 불러오는 중…</div> : null;
  const h = state.data;
  const s = summarizeRegion(h, sido);
  if (!s) return null;
  const data = s.recent30.map((d) => ({ ...d, label: md(d.date) }));
  const v = s.vs_normal;
  const w = s.week_vs_normal;
  // 기온 축: 정수 눈금이 되게 최저·최고에서 1도씩 여유
  const temps = data.flatMap((d) => [d.temp_max, d.temp_min]).filter((x) => x != null);
  const yDomain = temps.length ? [Math.floor(Math.min(...temps)) - 1, Math.ceil(Math.max(...temps)) + 1] : [0, 1];

  return (
    <div className="recent-weather">
      <div className="rw-head">
        <b>{sido} 지난 날씨</b>
        <span className="muted small">
          기상청 관측 · {md(s.last.date)}까지{h.sample && " · 예시 데이터"}
        </span>
      </div>
      {s.stale_days > 2 && <p className="small rw-stale">관측 자료가 {s.stale_days}일 늦어요 (마지막 {md(s.last.date)})</p>}

      <div className="rw-stats">
        <div><span className="muted small">{md(s.last.date)}</span><b>{t(s.last.temp_min)} / {t(s.last.temp_max)}</b><span className="small">비 {s.last.rain_mm ?? "—"}mm</span></div>
        <div><span className="muted small">최근 7일 비</span><b>{s.week_rain}mm</b><span className="small">{s.dry_days ? `비 안 온 날 ${s.dry_days}일째` : s.last.rain_mm == null ? "\u00a0" : `${md(s.last.date)} 비 옴`}</span></div>
        {w ? (
          <div title="1991~2020년 같은 날짜(앞뒤 3일) 평균과 비교">
            <span className="muted small">최근 7일 평년 대비</span>
            <b className={tone(w.temp_diff)}>{signed(w.temp_diff)}℃</b>
            <span className="small">비 {w.rain}mm (평년 {w.normal_rain}mm)</span>
          </div>
        ) : (
          v && (
            <div>
              <span className="muted small">{monthName(v.month)} 평년 대비</span>
              <b className={tone(v.temp_diff)}>{v.temp_diff == null ? "—" : `${signed(v.temp_diff)}℃`}</b>
              <span className="small">비 평년의 {v.rain_pct ?? "—"}%</span>
            </div>
          )
        )}
      </div>

      <div className="rw-chart" aria-label={`${sido} 최근 30일 최고·최저 기온과 강수량`}>
        <div className="rw-key small">
          <span>최근 30일</span>
          <span><i style={{ background: HI }} />최고</span>
          <span><i style={{ background: LO }} />최저</span>
          <span><i className="sq" style={{ background: RAIN }} />비(mm)</span>
        </div>
        <ResponsiveContainer width="100%" height={110}>
          <LineChart data={data} syncId="rw" margin={{ top: 6, right: 6, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#eef0ec" />
            <XAxis dataKey="label" hide />
            <YAxis tick={{ fontSize: 10, fill: "#7a817b" }} tickLine={false} axisLine={false} width={30} unit="°" domain={yDomain} tickCount={4} allowDecimals={false} />
            <Tooltip content={<TempTip />} cursor={{ stroke: "#c9cec6" }} />
            <Line dataKey="temp_max" stroke={HI} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} connectNulls={false} />
            <Line dataKey="temp_min" stroke={LO} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
        <ResponsiveContainer width="100%" height={58}>
          <BarChart data={data} syncId="rw" margin={{ top: 2, right: 6, left: 0, bottom: 0 }}>
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#7a817b" }} tickLine={false} axisLine={{ stroke: "#dfe3dc" }} interval={6} />
            <YAxis tick={{ fontSize: 10, fill: "#7a817b" }} tickLine={false} axisLine={false} width={30} tickCount={3} allowDecimals={false} />
            <Tooltip content={<TempTip />} cursor={{ fill: "rgba(0,0,0,0.04)" }} />
            <Bar dataKey="rain_mm" fill={RAIN} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {w && v && v.temp != null && (
        <p className="small muted" style={{ margin: 0 }}>
          {monthName(v.month)}: 평균 {v.temp}℃ (평년보다 {signed(v.temp_diff)}℃) · 비 {v.rain}mm (평년의 {v.rain_pct ?? "—"}%)
        </p>
      )}
      {s.signals.length > 0 && (
        <div className="rw-signals">
          {s.signals.map((x) => (
            <span key={x.text} className="rw-signal small" title={x.tip}>{x.icon} {x.text} <span className="muted">· {x.tip}</span></span>
          ))}
        </div>
      )}
    </div>
  );
}
