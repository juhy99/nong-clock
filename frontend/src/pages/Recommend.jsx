import { Fragment, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getCropInfo, getCropPricePath, getRecommendCrops, recommendCrops } from "../api/ml";
import { Async, useAsync } from "../components/common";
import { LAND_TYPES, SIDO_LIST, marketsInSido } from "../mocks/recommend";
import { PH_DEMOTE_GAP, SOIL_PH, phOf, soilPhFromPrev } from "../mocks/soil_ph";
import { addDays, daysBetween, md, shortDate, todayIso, won, wonPerKg } from "../utils/format";

const START_DAYS = 30; // 농사 시작 날짜: 오늘부터 30일 안
const SAMPLE_CROPS = { open: "대파·시금치·양파·봄동", house: "토마토·오이·상추·딸기", paddy: "쌀·콩", orchard: "사과·배·복숭아" };

/** 1234만 → "1,234만원", 1.2억 이상 → "1.2억원" (원 단위 입력) */
const man = (v) => {
  const m = v / 1e4;
  return Math.abs(m) >= 1e4 ? `${(m / 1e4).toFixed(1).replace(/\.0$/, "")}억원` : `${won(m)}만원`;
};
/** "2026-02-14" → "2월 중순" */
const third = (iso) => {
  const d = new Date(`${iso}T00:00:00`);
  const x = d.getDate();
  return `${d.getMonth() + 1}월 ${x <= 10 ? "상순" : x <= 20 ? "중순" : "하순"}`;
};
/** 일수 → "20일" / "2.5개월" / "1년" */
const dur = (days) => (days < 60 ? `${days}일` : days >= 330 ? `${Math.round(days / 365) || 1}년` : `${(days / 30.44).toFixed(1).replace(/\.0$/, "")}개월`);
const MAX_SPAN = 400; // 재배 기간 막대가 보여 주는 최대 일수 (보관이 더 길면 화살표로)

/** 재배 기간 막대 눈금: 시작일부터 매달 1일 위치(%) */
function spanTicks(start, span) {
  const out = [];
  const d = new Date(`${start}T00:00:00`);
  for (let k = 1; k <= 15; k++) {
    const m = new Date(d.getFullYear(), d.getMonth() + k, 1);
    const iso = `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}-01`;
    const x = daysBetween(start, iso);
    if (x >= span) break;
    out.push({ x: (x / span) * 100, mon: m.getMonth() + 1 });
  }
  // 달 이름은 두 눈금 사이 가운데에 (첫 달은 시작일~첫 눈금)
  const edges = [0, ...out.map((t) => t.x), 100];
  out.labels = edges.slice(0, -1).map((a, i) => {
    const mon = i < out.length ? (out[i].mon + 10) % 12 + 1 : out[out.length - 1].mon;
    return { x: (a + edges[i + 1]) / 2, w: edges[i + 1] - a, label: `${mon}월`, jan: mon === 1 };
  }).filter((l) => l.w > 6);
  return out;
}

/** 재배 기간 막대: 자람(연한 초록) → 수확(진한 초록) → 보관(주황 빗금) */
function GrowBar({ r, start, span, ticks }) {
  const pct = (a, b) => (Math.max(0, Math.min(daysBetween(start, b), span) - Math.min(daysBetween(start, a), span)) / span) * 100;
  const x0 = (daysBetween(start, r.plant_date) / span) * 100;
  const g = pct(r.plant_date, r.harvest_start), h = pct(r.harvest_start, r.harvest_end), st = pct(r.harvest_end, r.storage_end);
  const cut = daysBetween(start, r.storage_end) > span;
  const grow = daysBetween(r.plant_date, r.harvest_start), harv = daysBetween(r.harvest_start, r.harvest_end);
  return (
    <div className="rc-gb">
      <div className="rc-gb-txt">
        <span className="muted">심기</span> <b>{md(r.plant_date)}</b>
        <span className="muted"> → 수확</span> <b>{md(r.harvest_start)} ~ {md(r.harvest_end)}</b>
        <span className="muted"> · 재배 {dur(grow + harv)}</span>
      </div>
      <div className="rc-gb-bar" title={`심기 ${md(r.plant_date)} · 첫 수확 ${md(r.harvest_start)} · 수확 끝 ${md(r.harvest_end)} · 보관 ~${md(r.storage_end)}`}>
        {ticks.map((t) => <i key={t.x} className="tick" style={{ left: `${t.x}%` }} />)}
        <i className="seg grow" style={{ left: `${x0}%`, width: `${g}%` }} />
        <i className="seg harv" style={{ left: `${x0 + g}%`, width: `${h}%` }} />
        <i className={`seg store ${cut ? "cut" : ""}`} style={{ left: `${x0 + g + h}%`, width: `${st}%` }} />
      </div>
      <div className="rc-gb-leg">
        <span><i className="grow" />자람 {dur(grow)}</span>
        <span><i className="harv" />수확 {dur(harv)} {r.multi_harvest ? "(계속 따기)" : "(한 번에)"}</span>
        <span><i className="store" />보관 {dur(r.storage_days)}{cut ? " →" : ""}</span>
      </div>
    </div>
  );
}

const toPyeongText = (py) => `${((py * 3.3058) / 100).toFixed(1)}a`;

/** 주 단위 날짜 중 달이 바뀌는 첫 날만 눈금으로 (같은 달 이름이 두 번 나오지 않게) */
const monthTicks = (dates) => dates.filter((d, i) => i === 0 || d.slice(0, 7) !== dates[i - 1].slice(0, 7));
const monthLabel = (d) => `${new Date(`${d}T00:00:00`).getMonth() + 1}월`;

function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** 작물의 앞으로 13개월 예상 도매가 + 수확 기간 음영 */
function PriceChart({ crop, harvest, plant, factor = 1 }) {
  const state = useAsync(() => getCropPricePath(crop), [crop]);
  const f = (v) => Math.round(v * factor); // 고른 도매시장 가격 = 전국 평균 × 시장 계수
  const rows = (state.data?.points ?? []).map((p) => ({ date: p.date, price: f(p.price), range: [f(p.lower), f(p.upper)] }));
  if (!rows.length) return <div className="state">불러오는 중…</div>;
  const near = (iso) => rows.reduce((a, b) => (Math.abs(daysBetween(b.date, iso)) < Math.abs(daysBetween(a.date, iso)) ? b : a)).date;
  return (
    <ResponsiveContainer width="100%" height={230}>
      <ComposedChart data={rows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
        <XAxis dataKey="date" ticks={monthTicks(rows.map((r) => r.date))} tickFormatter={monthLabel} fontSize={12} interval="preserveStartEnd" minTickGap={10} />
        <YAxis fontSize={12} tickFormatter={won} width={60} domain={["auto", "auto"]} />
        <Tooltip formatter={(v, n) => (n === "range" ? `${won(v[0])} ~ ${won(v[1])}원` : wonPerKg(v))} labelFormatter={shortDate} />
        {harvest && <ReferenceArea x1={near(harvest[0])} x2={near(harvest[1])} fill="#e8f6ee" fillOpacity={1} label={{ value: "수확 기간", fontSize: 11, fill: "#0e7a45", position: "insideTop" }} />}
        {plant && <ReferenceLine x={near(plant)} stroke="#0e7a45" strokeDasharray="3 3" label={{ value: `심기 ${md(plant)}`, fontSize: 11, fill: "#0e7a45", position: "insideTopLeft" }} />}
        <Area name="range" dataKey="range" stroke="none" fill="#f7c3bf" fillOpacity={0.45} />
        <Line name="예상 판매가" dataKey="price" stroke="#e5483e" strokeWidth={2.2} strokeDasharray="6 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

const ym = (k) => `${Number(k.slice(5))}월`;

/** 토지 위치(시·도) → 그 시·도 안 도매시장끼리 비교 */
function RegionPicker({ region, setRegion }) {
  const { markets, none } = useMemo(() => marketsInSido(region), [region]);
  return (
    <div className="field">
      <label htmlFor="rc-region">토지 위치</label>
      <select id="rc-region" className="input" value={region} onChange={(e) => setRegion(e.target.value)}>
        {SIDO_LIST.map((k) => <option key={k} value={k}>{k}</option>)}
      </select>
      <span className="hint">
        {none
          ? <>{region}에는 공영 도매시장이 없어 <b>전국 도매시장 평균 가격</b>으로 계산해요</>
          : markets.length > 1
            ? <>{region} 도매시장 {markets.length}곳(<b>{markets.map((m) => m.name).join("·")}</b>)의 순이익을 비교해요</>
            : <>{region} 도매시장 <b>{markets[0].name}</b> 기준으로 계산해요</>}
      </span>
    </div>
  );
}

/** 만원 단위 금액 입력: 칸 안 "만원", 아래 원 환산 */
function ManwonInput({ value, onChange, label, aria = label }) {
  const [text, setText] = useState(value ? won(value) : "");
  useEffect(() => setText(value ? won(value) : ""), [value]);
  return (
    <label className="rc-money">
      <span className="lb">{label}</span>
      <span className="box">
        <input className="input" inputMode="numeric" placeholder="0" value={text} aria-label={`${aria} (만원)`}
          onChange={(e) => {
            const n = Number(e.target.value.replace(/[^0-9]/g, "").slice(0, 7)) || 0;
            setText(n ? won(n) : "");
            onChange(n);
          }} />
        <i>만원</i>
      </span>
      <small className={value ? "" : "muted"}>{value ? `= ${won(value * 10000)}원` : "없음"}</small>
    </label>
  );
}

/** 표 작물 칸 아래 pH 한 줄 */
function PhNote({ ph, soil }) {
  if (ph.kind === "lower") return <span className="rc-ph lower">pH {ph.min}~{ph.max} 필요 · 흙 약 {soil} → {ph.gap} 낮춰야</span>;
  if (ph.kind === "near") return <span className="rc-ph raise">pH {ph.min}~{ph.max} · 흙이 {ph.gap} 높지만 {PH_DEMOTE_GAP} 안쪽이라 그대로</span>;
  if (ph.kind === "raise") return <span className="rc-ph raise">pH {ph.min}~{ph.max} · 석회로 {ph.gap} 올리면 돼요</span>;
  if (ph.kind === "ok") return <span className="rc-ph ok">pH {ph.min}~{ph.max} · 지금 흙에 맞아요</span>;
  return <span className="rc-ph">pH 자료 없음</span>;
}

function MarketCompare({ o }) {
  return (
    <div className="rc-ship">
      <table className="table">
        <thead><tr><th>도매시장</th><th className="r">예상 판매가</th><th className="r">순이익</th><th className="r">마진률</th></tr></thead>
        <tbody>
          {o.market_compare.map((m) => (
            <tr key={m.code} className={m.best ? "selected" : ""}>
              <td>{m.name}{m.best && o.market_compare.length > 1 && <em className="rc-tag best">가장 높음</em>}</td>
              <td className="r num">{won(m.price_per_kg)}원</td>
              <td className="r num"><b className={m.margin < 0 ? "down" : ""}>{man(m.margin)}</b></td>
              <td className="r num">{Math.round(m.margin_rate)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      {o.no_market && <p className="hint" style={{ margin: "6px 0 0" }}>{o.region}에는 공영 도매시장이 없어 전국 도매시장 평균 가격으로 계산했어요</p>}
    </div>
  );
}

function OptionStats({ o, extra }) {
  const rent = o.land_rent + o.machine_rent;
  return (
    <>
      <div className="rc-kv">
        <div><span>{o.market.name} 예상가 (출하량 가중)</span><b>{wonPerKg(o.price_per_kg)}</b><em>전국 평균 {won(o.national_price_per_kg)}원 · 오차 ±{o.error_pct}%</em></div>
        <div><span>판매량</span><b>{o.sellable_t.toFixed(1)}t</b><em>수확 {o.yield_t.toFixed(1)}t{o.marketable_rate < 1 ? ` × 상품화율 ${Math.round(o.marketable_rate * 100)}%(추정)` : " · 10a당 " + o.yield_t_per_10a + "t"}</em></div>
        <div><span>예상 매출</span><b>{man(o.revenue)}</b><em>월별 출하량 × 월별 예상가</em></div>
        <div><span>총경영비</span><b>{man(o.cost)}</b><em>전국 평균 {man(o.base_cost)}{rent ? ` + 임대료 ${man(rent)}` : ""}</em></div>
        <div className="hl"><span>예상 순이익 (마진)</span><b>{man(o.margin)}</b><em>마진률 {Math.round(o.margin_rate)}% · 평당 {won(o.margin_per_pyeong)}원{extra}</em></div>
      </div>
      <div className="rc-scn">
        <div><span>가격 하락 (−{o.error_pct}%)</span><b className={o.margin_low < 0 ? "down" : ""}>{man(o.margin_low)}</b></div>
        <div className="mid"><span>기준</span><b>{man(o.margin)}</b></div>
        <div><span>가격 상승 (+{o.error_pct}%)</span><b>{man(o.margin_high)}</b></div>
      </div>
      <div className="rc-ship">
        <table className="table">
          <thead><tr><th>출하 달</th>{o.shipments.map((m) => <th key={m.month} className="r">{ym(m.month)}</th>)}<th className="r">합계</th></tr></thead>
          <tbody>
            <tr><td>판매량</td>{o.shipments.map((m) => <td key={m.month} className="r num">{m.t.toFixed(1)}t</td>)}<td className="r num"><b>{o.sellable_t.toFixed(1)}t</b></td></tr>
            <tr><td>예상가</td>{o.shipments.map((m) => <td key={m.month} className="r num">{won(m.price_per_kg)}</td>)}<td className="r num"><b>{won(o.price_per_kg)}</b></td></tr>
            <tr><td>매출</td>{o.shipments.map((m) => <td key={m.month} className="r num">{man(m.revenue)}</td>)}<td className="r num"><b>{man(o.revenue)}</b></td></tr>
          </tbody>
        </table>
      </div>
      <h3 className="rc-sub">{o.no_market ? "전국 도매시장 평균으로 팔면" : `${o.region} 도매시장별로 팔면`}</h3>
      <MarketCompare o={o} />
      <p className="hint rc-src">
        {o.rda
          ? <>농진청 2024 조사표 「{o.rda.row}」 10a당: 총수입 {man(o.rda.revenue)} · 경영비 {man(o.rda.cost)} · 소득 {man(o.rda.income)} → 이 계획 10a당: 매출 {man(o.per_10a.revenue)} · 경영비 {man(o.per_10a.cost)} · 순이익 {man(o.per_10a.income)} (임대료 빼고){o.source === "est" ? " · 이 작형 수량·경영비는 조사표 값을 작형에 맞춘 추정" : ""}</>
          : <>조사표에 없는 작물이라 수량·경영비·상품화율·가격 수준이 모두 <b>추정값</b>이에요.</>}
        {" "}출하 비중·계절 가격 모양은 추정이에요. 경영비(전국 평균)에는 고용 인건비는 들어 있지만 자가노동비는 빠져 있어요.
      </p>
    </>
  );
}

/* ───────── ① 내 땅으로 작물 고르기 ───────── */
export const DEFAULT_FORM = {
  lands: { open: 1200, house: 600, paddy: 0, orchard: 0 },
  rents: {}, // { open: { land: 만원, machine: 만원 } }
  prevs: {}, // { open: "상추" } 토지마다 기존에 키우던 작물 (조건표 이름)
  region: "경기",
  startOffset: 7, // 오늘부터 며칠 뒤 시작
};
export const formRequest = (f, today) => ({
  lands: Object.entries(f.lands).filter(([, v]) => v > 0).map(([t, v]) => ({
    type: t, area_pyeong: v, land_rent: f.rents[t]?.land ?? 0, machine_rent: f.rents[t]?.machine ?? 0, prev_crop: f.prevs[t] || null,
  })),
  start_date: addDays(today, f.startOffset), region: f.region,
});

function LandPicker({ form, setForm, goInfo }) {
  const today = todayIso();
  const { lands, rents, prevs, region } = form;
  const start = addDays(today, form.startOffset);
  const set = (patch) => setForm({ ...form, ...patch });
  const setLands = (v) => set({ lands: v });
  const setRegion = (v) => set({ region: v });
  const [sort, setSort] = useState("margin");
  const [type, setType] = useState("all");
  const [pick, setPick] = useState(null);
  const debForm = useDebounced(form);
  const req = useMemo(() => formRequest(debForm, today), [debForm, today]);
  const setRent = (t, k, v) => set({ rents: { ...rents, [t]: { ...rents[t], [k]: Math.max(0, Number(v) || 0) } } });
  const setPrevCrop = (t, v) => set({ prevs: { ...prevs, [t]: v } });
  const state = useAsync(() => (req.lands.length ? recommendCrops(req) : Promise.resolve({ results: [], unavailable: [] })), [JSON.stringify(req)]);
  const pickStart = (d) => d && set({ startOffset: Math.min(Math.max(daysBetween(today, d), 0), START_DAYS) });
  const total = Object.values(lands).reduce((s, v) => s + v, 0);

  const d = state.data;
  const types = d ? [...new Set(d.results.map((r) => r.land_type))] : [];
  const shown = (d?.results ?? []).filter((r) => type === "all" || r.land_type === type).sort((a, b) => a.demoted - b.demoted || b[sort] - a[sort]);
  const top = shown.find((r) => !r.demoted) ?? shown[0];
  const sel = shown.find((r) => r.crop === pick) ?? top;
  const span = Math.min(MAX_SPAN, Math.max(240, ...shown.map((r) => daysBetween(start, r.storage_end))));
  const ticks = spanTicks(start, span);

  return (
    <div className="predict-layout rc-layout">
      <section className="card" style={{ display: "grid", gap: 18 }}>
        <RegionPicker region={region} setRegion={setRegion} />
        <div className="field">
          <label>보유 토지와 평수</label>
          <div style={{ display: "grid", gap: 8 }}>
            {Object.entries(LAND_TYPES).map(([k, label]) => (
              <label key={k} className={`rc-land ${lands[k] > 0 ? "on" : ""}`}>
                <input type="checkbox" checked={lands[k] > 0} onChange={(e) => setLands({ ...lands, [k]: e.target.checked ? lands[k] || 300 : 0 })} />
                <span><b>{label}</b><small>{SAMPLE_CROPS[k]} 등</small></span>
                <span className="rc-py">
                  <input className="input" type="number" min="0" step="50" value={lands[k]} aria-label={`${label} 평수`} onChange={(e) => setLands({ ...lands, [k]: Math.max(0, Number(e.target.value) || 0) })} /> 평
                </span>
              </label>
            ))}
          </div>
          <span className="hint">{total ? `합계 ${won(total)}평 (${toPyeongText(total)})` : "토지를 하나 이상 골라 주세요"}</span>
        </div>
        <div className="field">
          <label>토지별 정보 <small className="muted">기존 작물은 선택 · 임대료는 이번 작기</small></label>
          <div style={{ display: "grid", gap: 10 }}>
            {Object.entries(LAND_TYPES).filter(([k]) => lands[k] > 0).map(([k, label]) => {
              const ph = prevs[k] ? soilPhFromPrev(prevs[k]) : null;
              return (
                <div key={k} className="rc-landinfo">
                  <b className="ttl">{label} <small className="muted">{won(lands[k])}평</small></b>
                  <label className="rc-prevsel">
                    <span className="lb">기존에 키우던 작물</span>
                    <select className="input" value={prevs[k] ?? ""} aria-label={`${label} 기존 작물`} onChange={(e) => setPrevCrop(k, e.target.value)}>
                      <option value="">없음</option>
                      {SOIL_PH.map((p) => <option key={p.name} value={p.name}>{p.name}{p.min != null ? ` · pH ${p.min}~${p.max}` : " · pH 자료 없음"}</option>)}
                    </select>
                    {prevs[k] && <small className="muted">{ph != null ? `흙 pH 약 ${ph}로 어림 (범위 가운데)` : "pH 자료가 없어 비교하지 않아요"}</small>}
                  </label>
                  <div className="rc-money2">
                    <ManwonInput label="토지 임차료" aria={`${label} 토지 임차료`} value={rents[k]?.land ?? 0} onChange={(v) => setRent(k, "land", v)} />
                    <ManwonInput label="농기계·시설 임차료" aria={`${label} 농기계·시설 임차료`} value={rents[k]?.machine ?? 0} onChange={(v) => setRent(k, "machine", v)} />
                  </div>
                </div>
              );
            })}
          </div>
          <span className="hint">
            기존 작물을 고르면 그 작물 알맞은 pH 범위의 가운데로 흙 pH를 어림해요. 흙 pH가 후보 작물의 최고값보다 {PH_DEMOTE_GAP} 이상 높으면 pH를 내리는 데 몇 달이 걸려서 순이익과 상관없이 맨 아래로 내려요.
            임대료는 그 토지 작물의 경영비에 그대로 더해요.
          </span>
        </div>
        <div className="field">
          <label htmlFor="rc-start">농사 시작 날짜</label>
          <input id="rc-start" type="date" className="input" value={start} min={today} max={addDays(today, START_DAYS)} onChange={(e) => pickStart(e.target.value)} />
          <div className="pills">
            {[[0, "오늘"], [7, "1주 뒤"], [14, "2주 뒤"], [30, "한 달 뒤"]].map(([n, l]) => (
              <button key={n} className={`pill sm ${daysBetween(today, start) === n ? "on" : ""}`} onClick={() => pickStart(addDays(today, n))}>{l}</button>
            ))}
          </div>
          <span className="hint">오늘부터 {START_DAYS}일 안에서 고를 수 있어요</span>
        </div>
        {top && (
          <div className="summary-box">
            <span className="summary-img">{top.emoji}</span>
            <div className="muted small">마진 1위 · {LAND_TYPES[top.land_type]} {won(top.area_pyeong)}평</div>
            <div className="price">{top.crop_name}</div>
            <div className="small">예상 마진 <b>{man(top.margin)}</b> · 마진률 <b className="rc-rate">{Math.round(top.margin_rate)}%</b></div>
            <div className="muted small">재배 {third(top.plant_date)} ~ {third(top.harvest_end)} · 보관 {dur(top.storage_days)}</div>
          </div>
        )}
      </section>

      <div className="rc-col">
        <section className="card">
          <div className="card-head">
            <div><h2>심을 수 있는 작물</h2><p>{shortDate(start)} 시작 · {d?.no_market ? <>{region}에 공영 도매시장이 없어 <b>전국 도매시장 평균 가격</b>으로 팔 때</> : <>{region} 도매시장 {d?.markets?.length ?? ""}곳 중 <b>순이익이 가장 높은 곳</b>에 팔 때</>} · {shown.length}개</p></div>
            <div className="seg">
              {[["margin", "순이익"], ["margin_rate", "마진률"], ["margin_per_pyeong", "평당 순이익"]].map(([k, l]) => (
                <button key={k} className={sort === k ? "on" : ""} onClick={() => setSort(k)}>{l}</button>
              ))}
            </div>
          </div>
          {types.length > 1 && (
            <div className="pills" style={{ marginBottom: 12 }}>
              {["all", ...types].map((t) => (
                <button key={t} className={`pill sm ${type === t ? "on" : ""}`} onClick={() => setType(t)}>
                  {t === "all" ? "전체" : LAND_TYPES[t]} {t === "all" ? d.results.length : d.results.filter((r) => r.land_type === t).length}
                </button>
              ))}
            </div>
          )}
          <Async state={{ ...state, data: shown.length ? shown : state.data && [] }} empty="이 날짜에 심을 수 있는 작물이 없어요. 날짜나 토지를 바꿔 보세요.">
            {(rows) => (
              <table className="table rc-table rc-fit">
                <colgroup><col style={{ width: 36 }} /><col style={{ width: "19%" }} /><col /><col style={{ width: "11%" }} /><col style={{ width: "13%" }} /><col style={{ width: "13%" }} /></colgroup>
                <thead>
                  <tr>
                    <th>#</th><th>작물</th>
                    <th>
                      <div className="rc-gb-head">
                        <span>재배 기간</span>
                        <span className="rc-gb-key"><i className="grow" />자람<i className="harv" />수확<i className="store" />보관</span>
                      </div>
                      <div className="rc-ruler">{ticks.labels.map((t) => <span key={t.x} className={t.jan ? "jan" : ""} style={{ left: `${t.x}%` }}>{t.label}</span>)}</div>
                    </th>
                    <th className="r">예상<br />판매가</th><th className="r">매출<br /><small>총경영비</small></th><th className="r">순이익<br /><small>마진률</small></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <Fragment key={r.crop}>
                    {r.demoted && !rows[i - 1]?.demoted && (
                      <tr className="rc-demote-head"><td colSpan={6}>⚠️ 흙 pH를 낮춰야 해서 아래로 내린 작물 — 기존 작물로 어림한 흙 pH가 이 작물들에 알맞은 pH보다 {PH_DEMOTE_GAP} 이상 높고, pH를 내리는 데는 몇 달이 걸려요</td></tr>
                    )}
                    <tr className={`clickable ${sel?.crop === r.crop ? "selected" : ""} ${r.demoted ? "rc-demoted" : ""}`} onClick={() => setPick(r.crop)}>
                      <td className="num">{i + 1}</td>
                      <td><span className="rc-crop"><span className="rc-emo">{r.emoji}</span><span><b>{r.crop_name}</b>{r.source === "est" && <em className="rc-est" title="수량·경영비가 공식 통계가 아닌 추정값">추정</em>}<small>{LAND_TYPES[r.land_type]} · {r.cropping}</small>{r.ph && <PhNote ph={r.ph} soil={r.soil_ph} />}</span></span></td>
                      <td><GrowBar r={r} start={start} span={span} ticks={ticks} /></td>
                      <td className="r num" data-label="예상 판매가">{won(r.price_per_kg)}원<small className="muted">/kg · {r.market.name}</small></td>
                      <td className="r num" data-label="매출 · 총경영비">{man(r.revenue)}<small className="muted">{man(r.cost)}</small></td>
                      <td className="r num rc-m" data-label="순이익"><b className={r.margin < 0 ? "down" : ""}>{man(r.margin)}</b><small className={r.margin_rate >= 0 ? "rc-rate" : "down"}>{Math.round(r.margin_rate)}%</small></td>
                    </tr>
                    </Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </Async>
          <div className="rc-more">
            <p className="hint" style={{ margin: 0 }}>줄을 누르면 아래에 그 작물의 가격 흐름과 경영비가 나와요. 막대 위에 마우스를 올리면 날짜가 나와요.</p>
            <button className="btn sm" onClick={() => goInfo(null)}>📖 추천에 없는 작물 보기 ›</button>
          </div>
        </section>

        {sel && (
          <section className="card">
            <div className="card-head">
              <div><h2>{sel.emoji} {sel.crop_name} · {sel.cropping}</h2><p>{shortDate(sel.plant_date)} 심기 → {shortDate(sel.harvest_start)} 첫 수확 → {shortDate(sel.harvest_end)} 수확 끝 · 보관 {dur(sel.storage_days)} · {LAND_TYPES[sel.land_type]} {won(sel.area_pyeong)}평</p></div>
              <button className="btn sm" onClick={() => goInfo(sel.crop)}>작물 정보 ›</button>
            </div>
            {sel.demoted && (
              <div className="rc-ph-box">
                <b>순위를 맨 아래로 내렸어요.</b> {LAND_TYPES[sel.land_type]} 토지의 기존 작물({sel.prev_crop})에 맞춰 온 흙은 pH 약 {sel.soil_ph}로 보이는데, {sel.crop_name}은(는) pH {sel.ph.min}~{sel.ph.max}가 알맞아요.
                pH를 {sel.ph.gap}만큼 내려야 하는데 황 등으로 낮추는 데는 보통 몇 달이 걸려서, 이번 작기에 바로 심기 어렵다고 봤어요. 순이익은 맞는 흙에서 키웠을 때 값이에요.
              </div>
            )}
            <OptionStats o={sel} />
            <PriceChart crop={sel.crop} harvest={[sel.harvest_start, sel.harvest_end]} plant={sel.plant_date} factor={sel.factor} />
            <p className="hint" style={{ margin: "6px 0 0" }}>점선 = 주 단위 예상 판매가, 붉은 띠 = 오차 범위, 초록 칸 = 수확 기간</p>
          </section>
        )}

        {d?.unavailable?.length > 0 && (
          <section className="card">
            <div className="card-head"><div><h2>지금은 심기 어려운 작물</h2><p>고른 날짜가 심는 시기가 아니거나 여러 해 기르는 작물이에요</p></div></div>
            <div className="pills">
              {d.unavailable.map((u) => (
                <span key={u.crop} className="pill sm rc-off">
                  {u.emoji} {u.crop_name}{" "}
                  <small>{u.next_plant_date ? `다음 심는 시기: ${shortDate(u.next_plant_date)}부터 (${u.next_cropping})` : u.reason}</small>
                </span>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

/* ───────── ② 작물 정보 ───────── */
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);
const doy = ([m, d]) => Math.round((new Date(2026, m - 1, d) - new Date(2026, 0, 1)) / 86400000);
const tenDay = ([m, d]) => `${m}월 ${d <= 10 ? "상순" : d <= 20 ? "중순" : "하순"}`;

/** 1년 달력 위 구간 [시작일(0~364), 길이] → 연말을 넘으면 둘로 나눔 */
function wrapSeg(start, len, cls) {
  const s0 = ((start % 365) + 365) % 365, l = Math.min(len, 365);
  if (s0 + l <= 365) return [{ left: s0, width: l, cls }];
  return [{ left: s0, width: 365 - s0, cls }, { left: 0, width: s0 + l - 365, cls }];
}

function CalendarRow({ w }) {
  const from = doy(w.plant_from), to = doy(w.plant_to);
  const winLen = ((to - from + 365) % 365) + 1;
  // 심는 기간 첫날에 심었을 때: 자람 → 수확 → 보관 (1년 안까지만)
  let left = 365;
  const segs = [];
  const add = (len, cls) => { const l = Math.max(0, Math.min(len, left)); segs.push(...wrapSeg(from + (365 - left), l, cls)); left -= l; };
  add(w.days_to_harvest, "grow"); add(w.harvest_days, "harv"); add(w.storage_days, "store");
  const pct = (v) => `${(v / 365) * 100}%`;
  return (
    <div className="ci-row">
      <div className="ci-name">
        <b>{w.name}</b>{w.source === "est" && <em className="rc-est">추정</em>}
        <small>심는 때 {tenDay(w.plant_from)} ~ {tenDay(w.plant_to)}</small>
      </div>
      <div className="ci-bar">
        {MONTHS.map((m) => <i key={m} className="tick" style={{ left: pct(doy([m, 1])) }} />)}
        {segs.map((g, i) => <i key={i} className={`seg ${g.cls}`} style={{ left: pct(g.left), width: pct(g.width) }} />)}
        {wrapSeg(from, winLen, "plant").map((g, i) => <i key={`p${i}`} className="seg plant" style={{ left: pct(g.left), width: pct(g.width) }} />)}
      </div>
      <div className="ci-nums">
        첫 수확까지 <b>{dur(w.days_to_harvest)}</b> · 수확 <b>{dur(w.harvest_days)}</b>{w.multi_harvest ? "(계속 따기)" : "(한 번에)"} · 보관 <b>{dur(w.storage_days)}</b>
        <span> · 10a당 {w.yield_t_per_10a}t · 경영비 {man(w.cost_per_10a)}</span>
      </div>
    </div>
  );
}

/** ① 탭 결과로 이 작물이 추천 몇 위인지, 빠졌다면 왜인지 (이유 문장은 /recommend/crops 응답의 excluded) */
function whyNot(crop, rec) {
  const i = rec.results.findIndex((r) => r.crop === crop.code);
  const ex = rec.excluded?.find((e) => e.crop === crop.code);
  if (ex) return { kind: ex.kind, text: ex.reason };
  if (i >= 0) return { kind: "in", text: `추천 ${i + 1}위에 있어요. 예상 마진률 ${Math.round(rec.results[i].margin_rate)}% · 순이익 ${man(rec.results[i].margin)}` };
  return { kind: "season", text: "추천 목록에 없어요." };
}

function CropInfo({ crop, setCrop, form, goLand }) {
  const today = todayIso();
  const list = useAsync(getRecommendCrops);
  const info = useAsync(() => getCropInfo(crop), [crop]);
  const req = useMemo(() => formRequest(form, today), [form, today]);
  const rec = useAsync(() => (req.lands.length ? recommendCrops(req) : Promise.resolve({ results: [], unavailable: [] })), [JSON.stringify(req)]);
  const c = list.data?.find((x) => x.code === crop);
  const d = info.data;
  const why = c && rec.data ? whyNot(c, rec.data) : null;
  const ph = phOf(crop);
  const owned = Object.entries(form.lands).filter(([, v]) => v > 0);

  return (
    <div className="ci">
      <section className="card">
        <div className="ci-pick">
          {(list.data ?? []).map((x) => (
            <button key={x.code} className={`pill sm ${x.code === crop ? "on" : ""}`} onClick={() => setCrop(x.code)}>{x.emoji} {x.name}</button>
          ))}
        </div>
      </section>
      {c && (
        <>
          <section className={`card ci-why ${why?.kind ?? ""}`}>
            <div className="ci-why-head">
              <h2>{c.emoji} {c.name} · 추천 결과</h2>
              <button className="link small" onClick={goLand}>입력 바꾸기 ›</button>
            </div>
            <p className="ci-why-txt">{why ? why.text : "불러오는 중…"}</p>
            <p className="hint" style={{ margin: 0 }}>
              ① 탭 입력 기준: {shortDate(addDays(today, form.startOffset))} 시작 · {form.region} · {owned.map(([k, v]) => `${LAND_TYPES[k]} ${won(v)}평`).join(" · ") || "토지 없음"}
            </p>
          </section>
          <section className="card">
            <div className="card-head"><div><h2>재배 조건</h2><p>작물 달력·수량·경영비는 농진청 2024 농산물소득조사와 농사로 재배력 기준 · "추정"은 공식 통계가 아닌 값</p></div></div>
            <div className="ci-facts">
              <div><span>재배할 수 있는 토지</span><b>{Object.entries(LAND_TYPES).map(([k, l]) => <em key={k} className={`ci-land ${k === c.land_type ? "on" : ""}`}>{l}</em>)}</b></div>
              <div><span>알맞은 흙 pH</span><b>{ph?.min != null ? `${ph.min} ~ ${ph.max}` : "자료 없음"}</b>{ph?.memo && <small>{ph.memo}</small>}</div>
              {d?.rda && <div><span>농진청 조사표 「{d.rda.row}」 10a당</span><b>수량 {won(d.rda.kg)}kg · 경영비 {man(d.rda.cost)}</b><small>총수입 {man(d.rda.revenue)} · 소득 {man(d.rda.income)}</small></div>}
              {d && !d.rda && !c.perennial && <div><span>10a당 수량·경영비</span><b>추정값 <em className="rc-est">추정</em></b><small>농진청 조사표에 없는 작물이에요</small></div>}
            </div>
            {d?.note ? <p className="ci-note">🌳 {d.note}</p> : (
              <div className="ci-cal">
                <div className="ci-head">
                  <span />
                  <div className="ci-months">{MONTHS.map((m) => <span key={m} style={{ left: `${((doy([m, 1]) + 15) / 365) * 100}%` }}>{m}<small>월</small></span>)}</div>
                </div>
                {(d?.croppings ?? []).map((w) => <CalendarRow key={w.name} w={w} />)}
                <div className="rc-gb-leg" style={{ marginTop: 8 }}>
                  <span><i className="plant" />심는 기간</span><span><i className="grow" />자람</span><span><i className="harv" />수확</span><span><i className="store" />보관</span>
                  <span className="muted">· 막대는 심는 기간 첫날에 심었을 때</span>
                </div>
              </div>
            )}
          </section>
          {!c.perennial && (
            <section className="card">
              <div className="card-head"><div><h2>앞으로 13개월 예상 도매가</h2><p>전국 도매시장 평균 · 원/kg · 붉은 띠 = 오차 범위</p></div></div>
              <PriceChart crop={crop} />
            </section>
          )}
        </>
      )}
    </div>
  );
}

/** 작물 추천 (/recommend?tab=land|info) — tab=crop(예전 링크)은 info 로 */
export default function Recommend() {
  const [params, setParams] = useSearchParams();
  const tab = ["info", "crop"].includes(params.get("tab")) ? "info" : "land";
  const crop = params.get("crop") || "tomato";
  const [form, setForm] = useState(DEFAULT_FORM); // ① 탭 입력 (작물 정보 탭이 이어받음)
  const set = (patch) => setParams({ tab, crop, ...patch }, { replace: true });
  const top = () => window.scrollTo({ top: 0, behavior: "smooth" });

  return (
    <div className="page">
      <div className="page-head">
        <h1>작물 추천</h1>
        <p>순이익(마진) = 월별 출하량 × 도매시장 월별 예상가 − 총경영비(전국 평균 경영비 + 임대료) · 수량·경영비·가격 수준은 농촌진흥청 2024년 농산물소득조사 10a당 전국 평균 · "추정" 표시는 공식 통계가 아닌 추정값</p>
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" className={tab === "land" ? "on" : ""} onClick={() => set({ tab: "land" })}>🧑‍🌾 내 땅으로 작물 고르기</button>
        <button role="tab" className={tab === "info" ? "on" : ""} onClick={() => set({ tab: "info" })}>📖 작물 정보</button>
      </div>
      {tab === "land" ? (
        <LandPicker form={form} setForm={setForm} goInfo={(c) => { set({ tab: "info", ...(c ? { crop: c } : {}) }); top(); }} />
      ) : (
        <CropInfo crop={crop} setCrop={(c) => set({ crop: c })} form={form} goLand={() => { set({ tab: "land" }); top(); }} />
      )}
      <div className="banner small">
        ⚠️
        <div>
          <b>계산 기준</b> · 수확한 지역 안의 도매시장에서 판다고 가정하고, 운송비와 유통 마진은 계산하지 않아요.
          수확이 멀수록 가격 예측 오차가 커져요(1~2개월 뒤 평균 약 17%, 6개월 이상 약 23%). 경영비는 전국 평균이라 내 농가와 다를 수 있어요. 마진은 참고용으로 보고 재배 경험·시설 조건·출하처를 함께 따져 보세요.
        </div>
      </div>
    </div>
  );
}
