import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getCropPricePath, getRecommendCrops, recommendCrops, recommendPlantingDates } from "../api/ml";
import { Async, useAsync } from "../components/common";
import { LAND_TYPES, SIDO_CENTER, marketsNear } from "../mocks/recommend";
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
        <XAxis dataKey="date" ticks={monthTicks(rows.map((r) => r.date))} tickFormatter={monthLabel} fontSize={12} interval={0} />
        <YAxis fontSize={12} tickFormatter={won} width={60} domain={["auto", "auto"]} />
        <Tooltip formatter={(v, n) => (n === "range" ? `${won(v[0])} ~ ${won(v[1])}원` : wonPerKg(v))} labelFormatter={shortDate} />
        <ReferenceArea x1={near(harvest[0])} x2={near(harvest[1])} fill="#e8f6ee" fillOpacity={1} label={{ value: "수확 기간", fontSize: 11, fill: "#0e7a45", position: "insideTop" }} />
        {plant && <ReferenceLine x={near(plant)} stroke="#0e7a45" strokeDasharray="3 3" label={{ value: `심기 ${md(plant)}`, fontSize: 11, fill: "#0e7a45", position: "insideTopLeft" }} />}
        <Area name="range" dataKey="range" stroke="none" fill="#f7c3bf" fillOpacity={0.45} />
        <Line name="예상 판매가" dataKey="price" stroke="#e5483e" strokeWidth={2.2} strokeDasharray="6 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

const ym = (k) => `${Number(k.slice(5))}월`;

/** 토지 위치(시·도) + 팔 도매시장 (기본: 가장 가까운 곳) */
function RegionPicker({ region, setRegion, market, setMarket }) {
  const near = useMemo(() => marketsNear(region), [region]);
  return (
    <div className="field">
      <label htmlFor="rc-region">토지 위치</label>
      <div className="rc-region">
        <select id="rc-region" className="input" value={region} onChange={(e) => { setRegion(e.target.value); setMarket(null); }}>
          {Object.keys(SIDO_CENTER).map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
        <select className="input" aria-label="팔 도매시장" value={market ?? ""} onChange={(e) => setMarket(e.target.value || null)}>
          <option value="">가까운 시장: {near[0].name} ({near[0].km}km)</option>
          {near.map((m) => <option key={m.code} value={m.code}>{m.name} · {m.km}km</option>)}
        </select>
      </div>
      <span className="hint">고른 도매시장의 예상 가격으로 매출·마진을 계산해요</span>
    </div>
  );
}

function MarketCompare({ o }) {
  const best = o.market_compare.filter((m) => m.code !== "national").reduce((a, b) => (b.margin > a.margin ? b : a));
  return (
    <div className="rc-ship">
      <table className="table">
        <thead><tr><th>도매시장</th><th className="r">거리</th><th className="r">예상 판매가</th><th className="r">순이익</th><th className="r">마진률</th></tr></thead>
        <tbody>
          {o.market_compare.map((m) => (
            <tr key={m.code} className={m.code === o.market.code ? "selected" : ""}>
              <td>{m.name}{m.code === o.market.code && <em className="rc-tag">판매 시장</em>}{m.code === best.code && <em className="rc-tag best">가장 높음</em>}</td>
              <td className="r num muted">{m.km == null ? "-" : `${m.km}km`}</td>
              <td className="r num">{won(m.price_per_kg)}원</td>
              <td className="r num"><b className={m.margin < 0 ? "down" : ""}>{man(m.margin)}</b></td>
              <td className="r num">{Math.round(m.margin_rate)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint" style={{ margin: "6px 0 0" }}>가까운 시장 4곳과 서울가락·전국 평균 비교 · 시장까지 운송비는 아직 빠져 있어요</p>
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
      <h3 className="rc-sub">도매시장별로 팔면</h3>
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
function LandPicker({ goCrop }) {
  const today = todayIso();
  const [lands, setLands] = useState({ open: 1200, house: 600, paddy: 0, orchard: 0 });
  const [rents, setRents] = useState({}); // { open: { land: 만원, machine: 만원 } }
  const [region, setRegion] = useState("충남");
  const [market, setMarket] = useState(null); // null = 가장 가까운 시장
  const [start, setStart] = useState(addDays(today, 7));
  const [sort, setSort] = useState("margin");
  const [type, setType] = useState("all");
  const [pick, setPick] = useState(null);
  const debounced = useDebounced(lands);
  const debRents = useDebounced(rents);
  const req = useMemo(
    () => ({
      lands: Object.entries(debounced).filter(([, v]) => v > 0)
        .map(([t, v]) => ({ type: t, area_pyeong: v, land_rent: debRents[t]?.land ?? 0, machine_rent: debRents[t]?.machine ?? 0 })),
      start_date: start, region, market,
    }),
    [debounced, debRents, start, region, market],
  );
  const setRent = (t, k, v) => setRents({ ...rents, [t]: { ...rents[t], [k]: Math.max(0, Number(v) || 0) } });
  const state = useAsync(() => (req.lands.length ? recommendCrops(req) : Promise.resolve({ results: [], unavailable: [] })), [JSON.stringify(req)]);
  const pickStart = (d) => d && setStart(addDays(today, Math.min(Math.max(daysBetween(today, d), 0), START_DAYS)));
  const total = Object.values(lands).reduce((s, v) => s + v, 0);

  const d = state.data;
  const types = d ? [...new Set(d.results.map((r) => r.land_type))] : [];
  const shown = (d?.results ?? []).filter((r) => type === "all" || r.land_type === type).sort((a, b) => b[sort] - a[sort]);
  const top = shown[0];
  const sel = shown.find((r) => r.crop === pick) ?? top;
  const span = Math.min(MAX_SPAN, Math.max(240, ...shown.map((r) => daysBetween(start, r.storage_end))));
  const ticks = spanTicks(start, span);

  return (
    <div className="predict-layout rc-layout">
      <section className="card" style={{ display: "grid", gap: 18 }}>
        <RegionPicker region={region} setRegion={setRegion} market={market} setMarket={setMarket} />
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
          <label>임대료 <small className="muted">이번 작기 · 만원 · 없으면 0</small></label>
          <div style={{ display: "grid", gap: 8 }}>
            {Object.entries(LAND_TYPES).filter(([k]) => lands[k] > 0).map(([k, label]) => (
              <div key={k} className="rc-rent">
                <b>{label}</b>
                <label>토지 <input className="input" type="number" min="0" step="10" value={rents[k]?.land ?? 0} aria-label={`${label} 토지 임차료`} onChange={(e) => setRent(k, "land", e.target.value)} /></label>
                <label>농기계·시설 <input className="input" type="number" min="0" step="10" value={rents[k]?.machine ?? 0} aria-label={`${label} 농기계·시설 임차료`} onChange={(e) => setRent(k, "machine", e.target.value)} /></label>
              </div>
            ))}
          </div>
          <span className="hint">넣은 금액을 그 토지 작물의 경영비에 그대로 더해요. 전국 평균 경영비에도 평균 임차료·위탁영농비가 조금 들어 있어 일부 겹칠 수 있어요.</span>
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
            <div><h2>심을 수 있는 작물</h2><p>{shortDate(start)} 시작 · <b>{d?.market?.name} 도매시장</b>에 팔 때 · {shown.length}개</p></div>
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
                    <tr key={r.crop} className={`clickable ${sel?.crop === r.crop ? "selected" : ""}`} onClick={() => setPick(r.crop)}>
                      <td className="num">{i + 1}</td>
                      <td><span className="rc-crop"><span className="rc-emo">{r.emoji}</span><span><b>{r.crop_name}</b>{r.source === "est" && <em className="rc-est" title="수량·경영비가 공식 통계가 아닌 추정값">추정</em>}<small>{LAND_TYPES[r.land_type]} · {r.cropping}</small></span></span></td>
                      <td><GrowBar r={r} start={start} span={span} ticks={ticks} /></td>
                      <td className="r num">{won(r.price_per_kg)}원<small className="muted">/kg</small></td>
                      <td className="r num">{man(r.revenue)}<small className="muted">{man(r.cost)}</small></td>
                      <td className="r num"><b className={r.margin < 0 ? "down" : ""}>{man(r.margin)}</b><small className={r.margin_rate >= 0 ? "rc-rate" : "down"}>{Math.round(r.margin_rate)}%</small></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Async>
          <p className="hint" style={{ margin: "10px 0 0" }}>줄을 누르면 아래에 그 작물의 가격 흐름과 경영비가 나와요. 막대 위에 마우스를 올리면 날짜가 나와요.</p>
        </section>

        {sel && (
          <section className="card">
            <div className="card-head">
              <div><h2>{sel.emoji} {sel.crop_name} · {sel.cropping}</h2><p>{shortDate(sel.plant_date)} 심기 → {shortDate(sel.harvest_start)} 첫 수확 → {shortDate(sel.harvest_end)} 수확 끝 · 보관 {dur(sel.storage_days)} · {LAND_TYPES[sel.land_type]} {won(sel.area_pyeong)}평</p></div>
              <button className="btn sm primary" onClick={() => goCrop(sel.crop, sel.area_pyeong)}>이 작물 가장 좋은 심는 날 찾기 ›</button>
            </div>
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

/* ───────── ② 작물로 심을 날짜 고르기 ───────── */
function PlantTooltip({ active, payload }) {
  const o = active && payload?.[0]?.payload?.o;
  if (!o) return null;
  return (
    <div className="card" style={{ padding: "8px 12px", fontSize: 13 }}>
      <b>{shortDate(o.plant_date)} 심기</b>
      <div>{o.cropping} · 재배 {third(o.plant_date)}~{third(o.harvest_end)}</div>
      <div>마진률 <b>{Math.round(o.margin_rate)}%</b> · 마진 {man(o.margin)}</div>
    </div>
  );
}

function CropPlanner({ crop, setCrop, area, setArea }) {
  const today = todayIso();
  const [rent, setRentState] = useState({ land: 0, machine: 0 });
  const [region, setRegion] = useState("충남");
  const [market, setMarket] = useState(null);
  const debRent = useDebounced(rent);
  const [metric, setMetric] = useState("margin_rate");
  const [selDate, setSelDate] = useState(null);
  const list = useAsync(getRecommendCrops);
  const debArea = useDebounced(area);
  const state = useAsync(() => (debArea > 0 ? recommendPlantingDates({ crop, area_pyeong: debArea, land_rent: debRent.land, machine_rent: debRent.machine, region, market }) : Promise.resolve(null)), [crop, debArea, debRent.land, debRent.machine, region, market]);
  useEffect(() => setSelDate(null), [crop]);
  const d = state.data;
  const info = list.data?.find((c) => c.code === crop);

  const live = (d?.points ?? []).filter((p) => p.option).map((p) => p.option);
  const tol = (v) => (metric === "margin_rate" ? 0.5 : Math.max(1, Math.abs(v) * 0.01));
  const best = live.reduce((a, b) => (!a || b[metric] > a[metric] + tol(a[metric]) ? b : a), null);
  const sel = live.find((o) => o.plant_date === selDate) ?? best;
  // 최고가 두 달 넘게 남았으면, 지금부터 60일 안에서 가장 좋은 날도 알려준다
  const soon = best && daysBetween(today, best.plant_date) > 60
    ? live.filter((o) => daysBetween(today, o.plant_date) <= 60).reduce((a, b) => (!a || b[metric] > a[metric] + tol(a[metric]) ? b : a), null)
    : null;
  const rows = (d?.points ?? []).map((p) => ({ date: p.plant_date, v: p.option ? p.option[metric] : null, o: p.option, cropping: p.option?.cropping }));
  // 심을 수 있는 구간(작형)마다 배경 칸
  const runs = [];
  rows.forEach((r, i) => {
    if (!r.o) return;
    const last = runs[runs.length - 1];
    if (last && last.end === i - 1 && last.name === r.cropping) last.end = i;
    else runs.push({ name: r.cropping, start: i, end: i });
  });
  const fmtV = (v) => (metric === "margin_rate" ? `${Math.round(v)}%` : man(v));

  return (
    <div className="predict-layout rc-layout">
      <section className="card" style={{ display: "grid", gap: 18 }}>
        <div className="field">
          <label htmlFor="rc-crop">작물</label>
          <select id="rc-crop" className="input" value={crop} onChange={(e) => setCrop(e.target.value)}>
            {(list.data ?? []).map((c) => <option key={c.code} value={c.code}>{c.emoji} {c.name}{c.perennial ? " (다년생)" : ""}</option>)}
          </select>
        </div>
        <div className="field">
          <label>토지</label>
          <div className="pills">{Object.entries(LAND_TYPES).map(([k, l]) => <span key={k} className={`pill sm ${info?.land_type === k ? "on" : ""}`} style={{ cursor: "default" }}>{l}</span>)}</div>
          <span className="hint">작물에 맞는 토지가 자동으로 정해져요</span>
        </div>
        <RegionPicker region={region} setRegion={setRegion} market={market} setMarket={setMarket} />
        <div className="field">
          <label htmlFor="rc-area">평수</label>
          <input id="rc-area" type="number" min="50" step="50" className="input" value={area} onChange={(e) => setArea(Math.max(0, Number(e.target.value) || 0))} />
          <span className="hint">{area ? `${toPyeongText(area)} · 10a의 ${(area / 302.5).toFixed(2)}배` : "평수를 입력해 주세요"}</span>
        </div>
        <div className="field">
          <label>임대료 <small className="muted">이번 작기 · 만원</small></label>
          <div className="rc-rent two">
            <label>토지 <input className="input" type="number" min="0" step="10" value={rent.land} onChange={(e) => setRentState({ ...rent, land: Math.max(0, Number(e.target.value) || 0) })} /></label>
            <label>농기계·시설 <input className="input" type="number" min="0" step="10" value={rent.machine} onChange={(e) => setRentState({ ...rent, machine: Math.max(0, Number(e.target.value) || 0) })} /></label>
          </div>
          <span className="hint">경영비에 그대로 더해요</span>
        </div>
        {best && (
          <div className="summary-box">
            <span className="summary-img">{info?.emoji}</span>
            <div className="muted small">가장 좋은 심는 날 · {best.cropping}</div>
            <div className="price">{shortDate(best.plant_date)}</div>
            <div className="small">
              {(() => { const n = daysBetween(today, best.plant_date); return n === 0 ? "오늘" : n <= 31 ? `${n}일 뒤` : `약 ${Math.round(n / 30)}개월 뒤`; })()} · 마진률 <b className="rc-rate">{Math.round(best.margin_rate)}%</b> · {man(best.margin)}
            </div>
            <div className="muted small">재배 {third(best.plant_date)} ~ {third(best.harvest_end)} · 보관 {dur(best.storage_days)}</div>
            {soon && (
              <button className="link small" style={{ marginTop: 6, padding: 0 }} onClick={() => setSelDate(soon.plant_date)}>
                가까운 날: {shortDate(soon.plant_date)} · 마진률 {Math.round(soon.margin_rate)}% ›
              </button>
            )}
          </div>
        )}
        {d?.note && (
          <div className="summary-box">
            <span className="summary-img">{info?.emoji}</span>
            <div className="price" style={{ fontSize: 18 }}>여러 해 기르는 작물</div>
            <div className="muted small">{d.note}. 심는 날보다 품종·묘목 선택이 중요해요.</div>
          </div>
        )}
      </section>

      <div className="rc-col">
        <section className="card">
          <div className="card-head">
            <div><h2>심는 날짜별 예상 {metric === "margin_rate" ? "마진률" : "마진"}</h2><p>앞으로 1년, 주 단위 · <b>{sel?.market?.name ?? best?.market?.name} 도매시장</b>에 팔 때 · 점을 누르면 그날 심었을 때 결과가 나와요</p></div>
            <div className="seg">
              {[["margin_rate", "마진률"], ["margin", "마진 금액"]].map(([k, l]) => <button key={k} className={metric === k ? "on" : ""} onClick={() => setMetric(k)}>{l}</button>)}
            </div>
          </div>
          <Async state={state} empty="평수를 입력해 주세요">
            {(res) =>
              res.note ? (
                <div className="state">다년생 작물은 심는 날짜별 비교를 하지 않아요</div>
              ) : (
                <>
                  <div className="rc-legend"><span><i style={{ background: "#e8f6ee", border: "1px solid #bfe3cc" }} />심을 수 있는 시기(작형)</span><span><i style={{ background: "#f2f3f0" }} />심는 시기 아님</span><span><i className="dotl" style={{ background: "var(--up)" }} />가장 좋은 날</span><span><i className="dotl" style={{ background: "var(--text)" }} />고른 날</span></div>
                  <ResponsiveContainer width="100%" height={280}>
                    <ComposedChart data={rows} margin={{ top: 16, right: 12, left: 0, bottom: 0 }} style={{ background: "#f6f7f4", borderRadius: 12 }}>
                      {runs.map((r) => (
                        <ReferenceArea key={`${r.name}-${r.start}`} x1={rows[r.start].date} x2={rows[r.end].date} fill="#e8f6ee" fillOpacity={1} ifOverflow="extendDomain"
                          label={{ value: r.name, position: "insideBottomLeft", fontSize: 11, fill: "#0e7a45" }} />
                      ))}
                      <CartesianGrid strokeDasharray="3 3" stroke="#e3e6df" vertical={false} />
                      <XAxis dataKey="date" ticks={monthTicks(rows.map((r) => r.date))} tickFormatter={monthLabel} fontSize={12} interval={0} />
                      <YAxis fontSize={12} width={64} tickFormatter={fmtV} />
                      <Tooltip content={<PlantTooltip />} />
                      <ReferenceLine x={rows[0]?.date} stroke="#1b1f1c" strokeDasharray="3 3" label={{ value: "오늘", fontSize: 11, position: "insideTopLeft" }} />
                      <Line
                        dataKey="v" stroke="#0e7a45" strokeWidth={2.2} connectNulls={false} isAnimationActive={false}
                        dot={(p) => {
                          if (p.value == null) return <g key={p.key} />;
                          const isB = p.payload.date === best?.plant_date, isS = p.payload.date === sel?.plant_date && !isB;
                          return (
                            <circle key={p.key} cx={p.cx} cy={p.cy} r={isB ? 7 : isS ? 6 : 4} fill={isB ? "#e5483e" : isS ? "#1b1f1c" : "#fff"} stroke={isB ? "#fff" : "#0e7a45"} strokeWidth={isB ? 2 : 1.6}
                              style={{ cursor: "pointer" }} onClick={() => setSelDate(p.payload.date)} />
                          );
                        }}
                        activeDot={false}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                  {best && <p className="hint" style={{ margin: "8px 0 0" }}>가장 좋은 날: <b className="up">{shortDate(best.plant_date)} · {fmtV(best[metric])}</b> (비슷하면 더 가까운 날을 골라요)</p>}
                </>
              )
            }
          </Async>
        </section>

        {sel && (
          <section className="card">
            <div className="card-head">
              <div>
                <h2>{shortDate(sel.plant_date)}에 심으면 {sel === best && <span className="pill sm on" style={{ cursor: "default" }}>가장 좋은 날</span>}</h2>
                <p>{sel.cropping} · {shortDate(sel.harvest_start)} 첫 수확 → {shortDate(sel.harvest_end)}까지 · {LAND_TYPES[sel.land_type]} {won(sel.area_pyeong)}평</p>
              </div>
            </div>
            <OptionStats o={sel} extra={sel !== best && best ? ` · 최고보다 ${Math.round(best.margin_rate - sel.margin_rate)}%p 낮음` : ""} />
            <PriceChart crop={sel.crop} harvest={[sel.harvest_start, sel.harvest_end]} plant={sel.plant_date} factor={sel.factor} />
          </section>
        )}

        {d?.top?.length > 0 && (
          <section className="card">
            <div className="card-head"><div><h2>추천 심는 날 TOP {d.top.length}</h2><p>작형마다 가장 좋은 날이에요. 줄을 누르면 위 그래프에서 그날이 선택돼요</p></div></div>
            <div className="table-wrap">
              <table className="table rc-table">
                <thead><tr><th>순위</th><th>심는 날</th><th>작형</th><th>재배 기간</th><th className="r">예상 판매가</th><th className="r">마진률</th><th className="r">예상 순이익</th></tr></thead>
                <tbody>
                  {d.top.map((o, i) => (
                    <tr key={o.plant_date} className={`clickable ${sel?.plant_date === o.plant_date ? "selected" : ""}`} onClick={() => setSelDate(o.plant_date)}>
                      <td>{i + 1}</td>
                      <td><b>{shortDate(o.plant_date)}</b></td>
                      <td>{o.cropping}</td>
                      <td>{third(o.plant_date)} ~ {third(o.harvest_end)} <small className="muted">({dur(daysBetween(o.plant_date, o.harvest_end))})</small></td>
                      <td className="r num">{won(o.price_per_kg)}원</td>
                      <td className="r num"><b className={o.margin_rate >= 0 ? "rc-rate" : "down"}>{Math.round(o.margin_rate)}%</b></td>
                      <td className="r num"><b>{man(o.margin)}</b></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

/** 작물 추천 (/recommend?tab=land|crop) */
export default function Recommend() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "crop" ? "crop" : "land";
  const crop = params.get("crop") || "tomato";
  const area = params.has("area") ? Math.max(0, Number(params.get("area")) || 0) : 600;
  const set = (patch) => setParams({ tab, crop, area: String(area), ...patch }, { replace: true });

  return (
    <div className="page">
      <div className="page-head">
        <h1>작물 추천</h1>
        <p>순이익(마진) = 월별 출하량 × 고른 도매시장의 월별 예상가 − 총경영비(전국 평균 경영비 + 임대료) · 수량·경영비·가격 수준은 농촌진흥청 2024년 농산물소득조사 10a당 전국 평균 · "추정" 표시는 공식 통계가 아닌 추정값</p>
      </div>
      <div className="tabs" role="tablist">
        <button role="tab" className={tab === "land" ? "on" : ""} onClick={() => set({ tab: "land" })}>🧑‍🌾 내 땅으로 작물 고르기</button>
        <button role="tab" className={tab === "crop" ? "on" : ""} onClick={() => set({ tab: "crop" })}>📅 작물로 심을 날짜 고르기</button>
      </div>
      {tab === "land" ? (
        <LandPicker goCrop={(c, a) => { set({ tab: "crop", crop: c, area: String(a) }); window.scrollTo({ top: 0, behavior: "smooth" }); }} />
      ) : (
        <CropPlanner crop={crop} setCrop={(c) => set({ crop: c })} area={area} setArea={(a) => set({ area: String(a) })} />
      )}
      <div className="banner small">
        ⚠️
        <div>수확이 멀수록 가격 예측 오차가 커져요(1~2개월 뒤 평균 약 17%, 6개월 이상 약 23%). 경영비는 전국 평균이라 내 농가와 다를 수 있어요. 마진은 참고용으로 보고 재배 경험·시설 조건·출하처를 함께 따져 보세요.</div>
      </div>
    </div>
  );
}
