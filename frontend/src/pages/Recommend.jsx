import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getCropInfo, getCropPricePath, getRecommendCrops, recommendCrops } from "../api/ml";
import { useAuth } from "../components/AuthContext";
import { Async, useAsync, useNarrow } from "../components/common";
import { LAND_TYPES, SIDO_LIST } from "../mocks/recommend";
import { SOIL_PH } from "../mocks/soil_ph";
import { IN50 } from "../mocks/items50";
import { addDays, daysBetween, md, todayIso, won } from "../utils/format";
import "./recommend.css";

/* ─────────────────────────────────────────────
   작물 추천 (v17, 11-11)  /recommend · /recommend?tab=info&crop=onion
   - 입력: 시·도 · 심을 날짜(오늘~1년) · 면적 · 기존에 키우던 작물(흙 pH 어림) · 1년 임대료 · 재배 방식 (11-13 날짜와 재배 방식 자리 바꿈)
   - 결과: 순이익 TOP3 카드. 추천 이유는 API 응답 값으로 만든 틀 문장만 (직접 쓴 설명 없음)
   - 작물 정보: 작물 고르기(드롭다운 검색) · 추천 결과 · 재배 조건 · 재배 달력 · 앞으로 12개월 예상 도매가
   - 11-13 실제 자료: 작물 34개 · 작형 = shared/crops.json (농사로 재배력 · 농진청 소득조사 · 통계청 생산비조사),
     가격 = DB AI 예측 도매가 × 농가 수취 비율 (예측이 없는 날은 평년 도매가, 쌀·콩은 조사 수취가), 시장 계수 = DB
   ───────────────────────────────────────────── */

const man = (v) => `${won(Math.round(v / 1e4))}만원`;
const f1 = (v) => Number(v).toFixed(1);
const mo = (iso) => Number(iso.slice(5, 7));
/** 11-17: 다른 해 날짜면 해를 붙임 — 쌀 '저장 가능 ~10/14'(다음 해)가 수확(10/15)보다 앞처럼 읽혔음 */
const mdy = (iso, ref) => (iso.slice(0, 4) !== ref.slice(0, 4) ? `${iso.slice(2, 4)}년 ${md(iso)}` : md(iso));
const DEFAULT_FORM = { region: "경기", type: "open", area: 1200, prev: "", rent: 0, date: todayIso() };

/** 가장 비싸게 팔리는 달 */
const bestMonth = (o) => o.shipments.reduce((a, b) => (b.price_per_kg > a.price_per_kg ? b : a));
const PH_LINE = {
  ok: (o) => `기존 작물(${o.prev_crop})로 본 흙 pH ${f1(o.soil_ph)} — 알맞은 범위(${f1(o.ph.min)}~${f1(o.ph.max)}) 안이에요`,
  raise: (o) => `기존 작물(${o.prev_crop})로 본 흙 pH ${f1(o.soil_ph)} — ${f1(o.ph.gap)} 올려야 해요 (석회로 맞출 수 있어요)`,
  near: (o) => `기존 작물(${o.prev_crop})로 본 흙 pH ${f1(o.soil_ph)} — 알맞은 범위보다 ${f1(o.ph.gap)} 높아요`,
  lower: (o) => `흙 pH를 ${f1(o.ph.gap)} 낮춰야 해서 순이익과 상관없이 아래로 내렸어요`,
  unknown: (o) => `${o.crop_name} 알맞은 pH 자료가 없어 흙 비교는 하지 않았어요`,
};
/** 추천 이유 틀 문장: 수확·저장 → 비싼 달 → 팔 시장 → 흙 pH (POST /recommend/crops 응답 값만으로) */
function reasonLines(o, region) {
  const b = bestMonth(o);
  const out = [
    `${md(o.harvest_start)}~${md(o.harvest_end)} 수확${o.storage_days > 0 ? `, 저장하면 ${mdy(o.storage_end, o.harvest_end)}까지 팔 수 있어요 (순수익은 수확 때 가격으로 계산)` : ", 저장 없이 바로 출하해요"}`,
    `가장 비싸게 팔리는 달은 ${mo(b.month + "-01")}월 (${won(b.price_per_kg)}원/kg)이에요`,
    o.no_market ? `${region}에는 공영 도매시장이 없어 전국 평균 가격으로 계산했어요` : `${region} 안에서는 ${o.market.name}에 팔 때 순이익이 가장 커요`,
  ];
  if (o.land_rent_year > 0) out.push(`임대료는 1년 ${man(o.land_rent_year)} 중 재배 기간 ${o.rent_days}일치 ${man(o.land_rent)}을 뺐어요`);
  if (o.ph) out.push(PH_LINE[o.ph.kind](o));
  const pl = priceLine(o);
  if (pl) out.push(pl);
  return out;
}
/** 가격 출처 (11-13): AI 예측 · 평년 도매가 · 조사 수취가 — 응답 price_basis 몫으로 */
function priceLine(o) {
  const b = o.price_basis ?? {};
  const pct = (v) => Math.round((v ?? 0) * 100);
  if (b.survey) return `가격은 ${o.rda?.source ?? "조사"} 농가 수취가(${won(o.price_per_kg)}원/kg)로 계산했어요 (도매시장 예측이 없는 작물)`;
  const ratio = o.farm_ratio ? ` · 농가가 받는 값 = 도매가 × ${o.farm_ratio.toFixed(2)}` : "";
  if (pct(b.forecast) >= 100) return `가격은 AI 예측 도매가(${o.forecast_base_date ? `${md(o.forecast_base_date)} 기준` : "최신"})로 계산했어요${ratio}`;
  if (pct(b.normal) >= 100) return `수확 때가 AI 예측이 없는 때(출하철 밖이거나 1년 뒤)라 평년(2021~2025) 도매가로 계산했어요${ratio}`;
  return `가격은 AI 예측 ${pct(b.forecast)}% · 예측이 없는 때(출하철 밖이거나 1년 뒤) 평년 도매가 ${pct(b.normal)}%로 계산했어요${ratio}`;
}
// 참고용 안내는 예측이 덜 정확한 작물·기간만 (수확이 멀다는 이유로는 띄우지 않음, 11-12)
// 11-16: 수확 철 값이 조사 가격의 2배를 넘으면 — 수량은 1년 평균 조사값이라 그 철엔 실제 수량이 적을 수 있음 (여름 시금치 등)
const refLine = (o) =>
  o.reference === "baseline" ? "이 작물·기간은 예측이 덜 정확해 참고용이에요"
  : o.peak_ratio ? `수확 철 값이 조사 평균의 ${o.peak_ratio.toFixed(1)}배예요. 수량은 1년 평균 조사값이라 이 철엔 실제 수확량이 적을 수 있어 참고용이에요`
  : "";

const request = (f) => ({
  region: f.region,
  lands: [{ type: f.type, area_pyeong: Number(f.area) || 1, land_rent: Number(f.rent) || 0, ...(f.prev ? { prev_crop: f.prev } : {}) }],
  start_date: f.date,
});

/* ── 입력 ── */
// 11-17 입력 상한 (ml-api schemas/recommend.py 와 같게): 면적 30만 평 · 1년 임대료 평당 2만원
const MAX_AREA = 300000, MAX_RENT_PER_PYEONG = 20000;
const formError = (d) => {
  const area = Number(d.area), rent = Number(d.rent) || 0;
  // 11-17: 지난 날짜·1년 넘는 날짜는 서버에 보내기 전에 (예전엔 서버 문장 "start_date 는 …"이 그대로 보였음)
  const today = todayIso();
  if (!d.date || d.date < today || d.date > addDays(today, 365)) return "심을 날짜는 오늘부터 1년 안으로 골라 주세요";
  if (!(area > 0)) return "면적을 1평 이상 넣어 주세요";
  if (area > MAX_AREA) return `면적은 ${won(MAX_AREA)}평까지 넣을 수 있어요`;
  if (rent < 0) return "임대료는 0 이상이어야 해요";
  if (rent * 10000 > area * MAX_RENT_PER_PYEONG) return `1년 임대료가 평당 ${won(MAX_RENT_PER_PYEONG)}원을 넘어요 (${won(area)}평이면 ${won(Math.floor((area * MAX_RENT_PER_PYEONG) / 10000))}만원까지)`;
  return "";
};

function LandForm({ form, onApply }) {
  const [d, setD] = useState(form);
  const set = (p) => setD((x) => ({ ...x, ...p }));
  const today = todayIso();
  const err = formError(d);
  return (
    <section className="card rc-form">
      <label className="rc-f"><span>시·도</span>
        <select className="input" value={d.region} onChange={(e) => set({ region: e.target.value })}>{SIDO_LIST.map((s) => <option key={s}>{s}</option>)}</select>
      </label>
      <label className="rc-f wide"><span>심을 날짜</span>
        <input className="input" type="date" min={today} max={addDays(today, 365)} value={d.date} onChange={(e) => e.target.value && set({ date: e.target.value })} />
      </label>
      <label className="rc-f"><span>면적 (평)</span>
        <input className="input" type="number" min="1" max={MAX_AREA} inputMode="numeric" value={d.area} onChange={(e) => set({ area: e.target.value })} aria-invalid={!!err && err.startsWith("면적")} />
      </label>
      <label className="rc-f"><span>기존에 키우던 작물 <Info>기존 작물로 흙 pH를 어림해서, 맞지 않는 작물은 아래로 내려요.</Info></span>
        <select className="input" value={d.prev} onChange={(e) => set({ prev: e.target.value })}>
          <option value="">없음 · 모름</option>
          {SOIL_PH.map((p) => <option key={p.name}>{p.name}</option>)}
        </select>
      </label>
      <label className="rc-f"><span>임대료 (1년, 만원) <Info>1년 임대료를 넣으면 심는 날부터 마지막 수확까지 기간만큼만 순수익에서 빼요 (예: 3개월이면 1/4). 내 땅이면 0을 넣으세요.</Info></span>
        <input className="input" type="number" min="0" inputMode="numeric" value={d.rent} onChange={(e) => set({ rent: e.target.value })} aria-invalid={!!err && err.includes("임대료")} />
      </label>
      <div className="rc-f"><span>재배 방식</span>
        <div className="pills">{Object.entries(LAND_TYPES).map(([k, l]) => <button key={k} type="button" className={`pill ${d.type === k ? "on" : ""}`} onClick={() => set({ type: k })}>{l}</button>)}</div>
      </div>
      {err && <p className="rc-err" role="alert">⚠️ {err}</p>}
      <button type="button" className="btn primary rc-go" disabled={!!err} onClick={() => onApply(d)}>다시 추천받기 →</button>
    </section>
  );
}

/** ⓘ 버튼: 누르면 짧은 설명 말풍선 (바깥을 누르거나 Esc 로 닫힘). 칸 이름 옆 자잘한 설명은 기본으로 감춘다
 *  말풍선은 칸 폭 안에서 왼쪽 맞춤 (휴대폰에서 화면 밖으로 안 나가게), 꼬리만 버튼 아래 (--ax) */
function Info({ children }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const off = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", off);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", off); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <span className="rc-info" ref={ref}>
      <button type="button" aria-label="설명 보기" aria-expanded={open} onClick={(e) => { e.preventDefault(); setOpen(!open); }}>i</button>
      {open && <span className="rc-tip" role="tooltip" style={{ "--ax": `${(ref.current?.offsetLeft ?? 0) + 4}px` }}>{children}</span>}
    </span>
  );
}

/** 카드 안 재배 달력: 심은 달부터 12개월 (심기 · 자람 · 수확 · 보관) */
function MiniCalendar({ o }) {
  const start = `${o.plant_date.slice(0, 8)}01`;
  const span = 365;
  const pos = (iso) => Math.max(0, Math.min(100, (daysBetween(start, iso) / span) * 100));
  const seg = (a, b, cls) => <i className={cls} style={{ left: `${pos(a)}%`, width: `calc(${Math.max(0.8, pos(b) - pos(a))}% - 2px)` }} />;
  const months = Array.from({ length: 12 }, (_, i) => ((mo(o.plant_date) - 1 + i) % 12) + 1);
  const store = o.storage_days > 0;
  return (
    <div className="rc-mini">
      {/* 휴대폰은 칸이 좁아 "월" 을 빼고 숫자만 */}
      <div className="mm">{months.map((m) => <span key={m}>{m}<i>월</i></span>)}</div>
      <div className="tr">
        {seg(o.plant_date, addDays(o.plant_date, 7), "s")}
        {seg(addDays(o.plant_date, 7), o.harvest_start, "g")}
        {seg(o.harvest_start, o.harvest_end, "h")}
        {store && seg(o.harvest_end, o.storage_end, "k")}
        <span className="pin" style={{ left: `${pos(o.plant_date)}%` }} />
      </div>
      <div className="ky"><span><i className="s" />심기</span><span><i className="g" />자람</span><span><i className="h" />수확</span>{store && <span><i className="k" />보관·출하</span>}</div>
      <div className="when">
        <div>심기<b>{md(o.plant_date)}</b></div>
        <div>수확<b>{md(o.harvest_start)}~{md(o.harvest_end)}</b></div>
        {store ? <div title="순수익은 수확 때 가격으로 계산했어요">저장 가능<b>~{mdy(o.storage_end, o.harvest_end)}</b></div> : <div>재배 기간<b>{daysBetween(o.plant_date, o.harvest_end)}일</b></div>}
      </div>
    </div>
  );
}

function CropCard({ o, rank, topProfit, topRate, goInfo }) {
  const [open, setOpen] = useState(rank === 0);
  const profit = o === topProfit, rate = o === topRate;
  return (
    <section className={`card rc-card ${open ? "open" : ""}`}>
      <span className={`rc-art ${profit ? "profit" : rate ? "rate" : ""}`}>
        <i aria-hidden>{o.emoji}</i>
        {profit && <b className="profit">💰 순수익 1위</b>}
        {rate && <b className="rate">📊 마진율 1위</b>}
      </span>
      <span className={`rc-n ${rank === 0 ? "first" : ""}`}>{String(rank + 1).padStart(2, "0")}</span>
      <div className="rc-nm">{o.crop_name}<small>{LAND_TYPES[o.land_type]} {o.cropping} · {mo(o.harvest_start)}월 수확</small></div>
      <div className="rc-money">
        <div className={profit ? "hi-profit" : ""}><span>예상 순수익</span><b>{man(o.margin)}</b></div>
        <div className={rate ? "hi-rate" : ""}><span>마진율</span><b>{Math.round(o.margin_rate)}%</b></div>
      </div>
      {refLine(o) && <span className="rc-ref">ⓘ {refLine(o)}</span>}
      <button type="button" className="rc-toggle" aria-expanded={open} onClick={() => setOpen(!open)}><span>📅 재배 달력 보기</span><span className="ar">▾</span></button>
      <div className="rc-exp"><div><MiniCalendar o={o} /></div></div>
      <div className="rc-acts">
        {IN50.has(o.crop) && <Link className="btn primary" to={`/ai?item=${o.crop}`}>{o.crop_name} 가격 예측 보기</Link>}
        <button type="button" className="btn" onClick={() => goInfo(o.crop)}>재배 정보 ›</button>
      </div>
    </section>
  );
}

/* ── 11-17 과수원: 나무는 심는 날 비교 대신 다 자란 나무 기준 1년 소득 (농진청 소득조사) ── */
const monthsText = (h) => (h ? (h[0] === h[1] ? `${h[0]}월` : `${h[0]}~${h[1]}월`) : "");
function OrchardResults({ list, goInfo }) {
  if (!list.length) return <div className="card state">과수원 작물 자료를 불러오지 못했어요.</div>;
  const top = list.slice(0, 3), rest = list.slice(3);
  const src = top[0].rda;
  return (
    <>
      <div className="card rc-note rc-orchard-note">
        🌳 과수원 나무는 한 번 심으면 여러 해 기르니 <b>심을 날짜 비교 대신 다 자란 나무에서 1년에 얻는 순수익</b>으로 줄 세웠어요.
        {src && ` 수량·가격·경영비는 ${src.source} ${src.years[0]}~${src.years.at(-1)}년 전국 평균이고, 가격에는 고른 시·도 도매시장이 전국보다 얼마나 비싼지(싼지)를 곱했어요.`} 새로 심으면 첫 수확까지 몇 해가 걸려요.
      </div>
      <div className="rc-top3">
        {top.map((o, i) => (
          <section key={o.crop} className="card rc-card open">
            <span className={`rc-art ${i === 0 ? "profit" : ""}`}><i aria-hidden>{o.emoji}</i>{i === 0 && <b className="profit">💰 순수익 1위</b>}</span>
            <span className={`rc-n ${i === 0 ? "first" : ""}`}>{String(i + 1).padStart(2, "0")}</span>
            <div className="rc-nm">{o.crop_name}<small>과수원 · 다 자란 나무 기준{o.harvest_months ? ` · ${monthsText(o.harvest_months)} 수확` : ""}</small></div>
            <div className="rc-money">
              <div className={i === 0 ? "hi-profit" : ""}><span>1년 순수익</span><b>{man(o.margin)}</b></div>
              <div><span>마진율</span><b>{Math.round(o.margin_rate)}%</b></div>
            </div>
            <ul className="rc-why">
              <li>1년 수확 {f1(o.yield_t)}톤 × {won(o.price_per_kg)}원/kg = 매출 {man(o.revenue)}</li>
              <li>경영비 {man(o.base_cost)}{o.land_rent > 0 ? ` + 임대료 1년 ${man(o.land_rent)}` : ""}</li>
              {/* 11-17: 시·도 안 도매시장 값 차이 반영 (수확 달 시장 계수 평균) */}
              {o.market && o.market !== "national" && (
                <li>팔 시장 {o.market_name} — 수확 철 값이 전국 평균의 {Math.round(o.market_factor * 100)}%라 조사 가격에 곱했어요</li>
              )}
            </ul>
            {o.region_note && <span className="rc-ref">ⓘ {o.region_note}</span>}
            <div className="rc-acts">
              {IN50.has(o.crop) && <Link className="btn primary" to={`/ai?item=${o.crop}`}>{o.crop_name} 가격 예측 보기</Link>}
              <button type="button" className="btn" onClick={() => goInfo(o.crop)}>재배 정보 ›</button>
            </div>
          </section>
        ))}
      </div>
      {rest.length > 0 && (
        <div className="card rc-rest">
          {rest.map((o, i) => (
            <button key={o.crop} type="button" className="rc-rest-row" onClick={() => goInfo(o.crop)}>
              <span>{String(i + 4).padStart(2, "0")} {o.emoji} {o.crop_name}</span>
              <span>1년 순수익 <b>{man(o.margin)}</b> · 마진율 {Math.round(o.margin_rate)}%{o.region_note ? " · ⓘ 주산지 밖" : ""}</span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

/* 11-17: 결과가 0개면 이유와 다음에 심을 수 있는 날을 보여 주고, 그 날로 바로 다시 보기 */
function NoResult({ d, form, retry }) {
  const max = addDays(todayIso(), 365);
  const next = d.unavailable.filter((u) => u.next_plant_date && u.next_plant_date <= max).sort((a, b) => a.next_plant_date.localeCompare(b.next_plant_date));
  const land = LAND_TYPES[form.type];
  return (
    <div className="card rc-few rc-none">
      <b>{md(form.date)}에 {land}에 심을 수 있는 작물이 없어요</b>
      {next.length ? (
        <>
          <p>{land}에서 비교하는 작물은 {d.unavailable.map((u) => u.crop_name).join("·")}이고, 심는 때가 정해져 있어요.</p>
          <ul>{next.map((u) => <li key={u.crop}>{u.emoji} {u.crop_name} — {u.next_cropping} <b>{md(u.next_plant_date)}부터</b></li>)}</ul>
          <button type="button" className="btn primary" onClick={() => retry(next[0].next_plant_date)}>{md(next[0].next_plant_date)}({next[0].crop_name})로 다시 보기 →</button>
        </>
      ) : <p>재배 방식이나 심을 날짜를 바꿔 보세요.</p>}
    </div>
  );
}

function Results({ state, form, goInfo, retry }) {
  return (
    <Async state={state} minHeight={360}>
      {(d) => {
        if (form.type === "orchard") return <OrchardResults list={d.orchards ?? []} goInfo={goInfo} />;
        const top = d.results.slice(0, 3);
        if (!top.length) return <NoResult d={d} form={form} retry={retry} />;
        const topProfit = top.reduce((a, b) => (b.margin > a.margin ? b : a));
        const topRate = top.reduce((a, b) => (b.margin_rate > a.margin_rate ? b : a));
        return (
          <>
            <div className="rc-top3">
              {top.map((o, i) => <CropCard key={o.crop + o.cropping} o={o} rank={i} topProfit={topProfit} topRate={topRate} goInfo={goInfo} />)}
              {top.length < 3 && (
                <div className="card rc-few">
                  <b>이 조건에서 심을 수 있는 작물은 {top.length}개예요</b>
                  <p>재배 방식을 더 고르거나 심을 날짜를 바꾸면 다른 작물도 볼 수 있어요.</p>
                  <button type="button" className="link" onClick={() => goInfo(top[0].crop)}>다른 작물 재배 정보 보기 ›</button>
                </div>
              )}
            </div>
          </>
        );
      }}
    </Async>
  );
}

/* ── 작물 정보 ── */
function CropPicker({ list, crop, ranks, onPick }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const box = useRef(null);
  useEffect(() => {
    const off = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", off);
    return () => document.removeEventListener("mousedown", off);
  }, []);
  const cur = list.find((c) => c.code === crop);
  const hits = list.filter((c) => !q.trim() || c.name.includes(q.trim()));
  const lands = (c) => (c.land_types?.length ? c.land_types : [c.land_type]); // 수박처럼 노지·시설 둘 다면 두 묶음에 (11-13)
  const groups = Object.entries(LAND_TYPES).map(([k, l]) => [l, hits.filter((c) => lands(c).includes(k))]).filter(([, cs]) => cs.length);
  const pick = (c) => { onPick(c); setOpen(false); setQ(""); };
  return (
    <section className="card rc-pick">
      <div className={`rc-combo ${open ? "open" : ""}`} ref={box}>
        <span className="lb">작물</span>
        <button type="button" className="input cb" onClick={() => setOpen(!open)} aria-expanded={open}>
          {cur ? <>{cur.emoji} {cur.name} <small>· {cur.land_type_name}</small></> : "작물 고르기"}
        </button>
        {open && (
          <div className="panel">
            <input className="input" autoFocus placeholder="작물 이름으로 찾기 (예: 양, 토마)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="작물 찾기" />
            {groups.map(([g, cs]) => (
              <div key={g} className="grp">
                <h4>{g} · {cs.length}</h4>
                <div className="its">
                  {cs.map((c) => (
                    <button key={g + c.code} type="button" className={c.code === crop ? "on" : ""} onClick={() => pick(c.code)}>
                      {c.name}{ranks[c.code] && <span className="rk">추천 {ranks[c.code]}위</span>}
                    </button>
                  ))}
                </div>
              </div>
            ))}
            {!groups.length && <p className="muted">'{q}'와 맞는 작물이 없어요</p>}
          </div>
        )}
      </div>
      {Object.keys(ranks).length > 0 && (
        <div className="rc-rec">
          <span className="lb">내가 추천받은 작물</span>
          <div className="pills">
            {Object.entries(ranks).sort((a, b) => a[1] - b[1]).slice(0, 3).map(([code, r]) => (
              <button key={code} type="button" className={`pill ${code === crop ? "on" : ""}`} onClick={() => pick(code)}>{r}위 {list.find((c) => c.code === code)?.name}</button>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

// 작물 정보 탭: 추천에 없는 이유 종류 → 배지 (11-13)
const OUT_LABEL = { perennial: "여러 해 기르는 나무", land: "고른 토지에서 못 길러요", season: "지금은 심는 때가 아니에요", ph: "흙 pH 때문에 맨 아래", low: "추천 3위 밖" };

function WhyCard({ crop, cropName, emoji, rec, form, info, goLand }) {
  const results = rec?.results ?? [];
  const rank = results.findIndex((r) => r.crop === crop);
  const o = rank >= 0 ? results[rank] : null;
  const ex = rec?.excluded?.find((e) => e.crop === crop);
  const cond = `입력한 조건 · ${form.region} · ${LAND_TYPES[form.type]} · ${won(form.area)}평 · 기존 작물 ${form.prev || "없음"} · 임대료 ${won(form.rent || 0)}만원 · ${form.date.replaceAll("-", ". ")}. 심기`;
  // 심는 기간 안 위치 (작물 정보 croppings 의 심는 기간과 심을 날짜로)
  const w = o && info?.croppings?.find((c) => c.name === o.cropping);
  const windowLine = w && (() => {
    const y = form.date.slice(0, 4);
    const iso = ([m, dd]) => `${y}-${String(m).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
    let end = iso(w.plant_to);
    if (end < form.date) end = `${Number(y) + 1}${end.slice(4)}`;
    const left = daysBetween(form.date, end);
    return left >= 0 && left <= 120 ? `${w.name} 심는 기간(${w.plant_from.join("/")}~${w.plant_to.join("/")}) 끝나기 ${left}일 전이에요` : null;
  })();
  return (
    <section className="card rc-whycard">
      <div className="rc-ch"><h2>{emoji} {cropName} · 추천 결과</h2><button type="button" className="link" onClick={goLand}>입력 바꾸기 ›</button></div>
      {o ? (
        <>
          <span className="rc-badge">🏆 내 조건에서 {rank + 1}위</span>
          <p className="rc-txt">{form.region} {LAND_TYPES[form.type]} {won(form.area)}평에 <b>{md(o.plant_date)}</b> 심으면 임대료를 빼고<br /><b>약 {man(o.margin)}</b>이 남을 것으로 보여요.</p>
          <div className="rc-nums"><div><span>예상 순수익</span><b>{man(o.margin)}</b></div><div><span>마진율</span><b>{Math.round(o.margin_rate)}%</b></div><div><span>수확</span><b>{md(o.harvest_start)}~{md(o.harvest_end)}</b></div></div>
          {refLine(o) && <span className="rc-ref">ⓘ {refLine(o)}</span>}
          <ul className="rc-why">{[...reasonLines(o, form.region), ...(windowLine ? [windowLine] : [])].map((t) => <li key={t}>{t}</li>)}</ul>
        </>
      ) : (
        <>
          <span className="rc-badge out">{OUT_LABEL[ex?.kind] ?? "추천 목록 밖"}</span>
          <p className="rc-txt">{ex ? ex.reason : rec ? "추천 목록에 없어요." : "추천 결과를 불러오는 중…"}</p>
        </>
      )}
      <p className="rc-cond">{cond}</p>
    </section>
  );
}

function Conditions({ info }) {
  const ph = info.soil_ph;
  const pct = (v) => ((v - 4) / 6) * 100; // pH 4 ~ 10 막대
  return (
    <section className="card">
      <h2>재배 조건</h2>
      <div className="rc-facts">
        <div><span>재배할 수 있는 토지</span>
          <div className="land">{Object.entries(LAND_TYPES).map(([k, l]) => <em key={k} className={(info.crop.land_types?.length ? info.crop.land_types : [info.crop.land_type]).includes(k) ? "on" : ""}>{l}</em>)}</div>
        </div>
        <div><span>알맞은 흙 pH</span>
          {ph?.min != null ? (
            <div>
              <b>{f1(ph.min)} ~ {f1(ph.max)}</b>
              <div className="ph"><i style={{ left: `${pct(ph.min)}%`, width: `${pct(ph.max) - pct(ph.min)}%` }} /></div>
              <div className="ph-ax"><span>4 산성</span><span>7 중성</span><span>알칼리 10</span></div>
              {ph.memo && <small>{ph.memo}</small>}
            </div>
          ) : <b>자료 없음</b>}
        </div>
        {info.rda ? (
          <div><span>{info.rda.source || "조사표"} 「{info.rda.row}」<br />{info.rda.years?.length ? `${info.rda.years[0]}~${info.rda.years.at(-1)} 평균 · ` : ""}10a당</span>
            <div><b>수량 {won(info.rda.kg)}kg · 경영비 {man(info.rda.cost)}</b><small>총수입 {man(info.rda.revenue)} · 소득 {man(info.rda.income)} · 농가 수취가 {won(info.rda.price)}원/kg</small></div>
          </div>
        ) : (
          <div><span>10a당 수량·경영비</span><div><b>자료 없음</b><small>조사표에 없는 작물이에요</small></div></div>
        )}
      </div>
    </section>
  );
}

/** 재배 달력 (1~12월): 작형마다 심는 기간 → 자람 → 수확 → 보관, 해를 넘기면 앞으로 이어 그림 */
function Calendar({ info, plantDate }) {
  if (info.note) return <section className="card"><h2>재배 달력</h2><p className="rc-note">🌳 {info.note}</p></section>;
  const doy = ([m, d]) => Math.round((new Date(2026, m - 1, d) - new Date(2026, 0, 1)) / 864e5);
  const segs = (a, len, cls) => {
    const s = ((a % 365) + 365) % 365, l = Math.min(len, 365);
    return s + l <= 365 ? [[s, l, cls]] : [[s, 365 - s, cls], [0, s + l - 365, cls]];
  };
  const LBL = { plant: "심기", grow: "자람", harv: "수확", store: "보관·출하" };
  const p = (v) => (v / 365) * 100;
  const today = plantDate ? doy([mo(plantDate), Number(plantDate.slice(8, 10))]) : null;
  const multiLand = new Set(info.croppings.map((c) => c.land)).size > 1;
  return (
    <section className="card">
      <div className="rc-ch"><h2>재배 달력</h2><small>작형별 · 심는 기간 첫날에 심었을 때 · 농사로 재배력</small></div>
      <div className="rc-cal">
        <div className="mh"><span /><div className="months">{Array.from({ length: 12 }, (_, i) => <span key={i}>{i + 1}월</span>)}</div></div>
        {info.croppings.map((c) => {
          const a = doy(c.plant_from), win = ((doy(c.plant_to) - a + 365) % 365) + 1;
          const list = [...segs(a, win, "plant"), ...segs(a + win, Math.max(0, c.days_to_harvest - win), "grow"), ...segs(a + c.days_to_harvest, c.harvest_days, "harv"),
            ...(c.storage_days ? segs(a + c.days_to_harvest + c.harvest_days, Math.min(c.storage_days, 365 - c.days_to_harvest - c.harvest_days), "store") : [])];
          return (
            <div className="row" key={c.name}>
              <span className="nm" title={c.schedule_source || undefined}>{multiLand ? `${LAND_TYPES[c.land] ?? ""} ` : ""}{c.name}{c.source === "est" && <em>추정</em>}<small>심는 때 {c.plant_from.join("/")}~{c.plant_to.join("/")}</small></span>
              <div className="track">{list.filter(([, l]) => l > 0).map(([s, l, k], i) => <i key={i} className={`k-${k}`} style={{ left: `${p(s)}%`, width: `calc(${p(l)}% - 3px)` }}>{p(l) > 7 ? LBL[k] : ""}</i>)}</div>
            </div>
          );
        })}
        {today != null && <div className="today" style={{ "--t": today / 365 }}><span>▲ {md(plantDate)} 내가 심을 날</span></div>}
      </div>
      <div className="rc-key"><span><i className="k-plant" />심는 기간</span><span><i className="k-grow" />자람</span><span><i className="k-harv" />수확</span><span><i className="k-store" />보관·출하</span></div>
    </section>
  );
}

/** 앞으로 12개월 예상 도매가 (53점, 주 단위) + 내 수확 기간 */
function PriceYear({ crop, harvest }) {
  const narrow = useNarrow();
  const state = useAsync(() => getCropPricePath(crop), [crop]);
  const pts = state.data?.points ?? [];
  if (state.error) return <section className="card state">가격을 불러오지 못했어요: {state.error.message}</section>;
  if (!pts.length) return state.data ? null : <section className="card state">불러오는 중…</section>;
  if (pts.every((x) => x.basis === "survey")) return (
    <section className="card">
      <div className="rc-ch"><h2>앞으로 12개월 예상 가격</h2><small>원/kg · 농가 수취가</small></div>
      <p className="rc-txt">도매시장 경매 가격이 없는 작물이라, 조사된 농가 수취가격 <b>{won(pts[0].price)}원/kg</b>(최근 3개 해 평균)으로 계산해요. 그래서 달마다 값이 바뀌지 않아요.</p>
    </section>
  );
  const allNormal = pts.every((x) => x.basis === "normal");
  // 11-13: 예측이 없는 날(평년 가격) · 출하철 밖(참고값) 알림
  const nNormal = pts.filter((x) => x.basis === "normal").length, nOff = pts.filter((x) => x.off_season).length;
  const note = [
    state.data.forecast_base_date && `AI 예측 ${md(state.data.forecast_base_date)} 기준`,
    nNormal > 0 && `${nNormal === pts.length ? "AI 예측이 없는 작물이라 모두" : "예측이 없는 날은"} 평년(2021~2025) 도매가`,
    nOff > 0 && "월 예측(12달)이 끝난 뒤의 값은 평년 × 비율로 낸 참고값",
  ].filter(Boolean).join(" · ");
  // 휴대폰: 좁은 그림으로 다시 그려 글씨가 작아지지 않게 (달 이름표는 3달마다)
  const W = narrow ? 420 : 1300, H = narrow ? 320 : 300, L = narrow ? 54 : 70, R = narrow ? 14 : 24, T = 36, B = 34;
  const vals = pts.flatMap((x) => [x.lower, x.upper]);
  const step = [50, 100, 200, 300, 500, 1000, 2000, 5000].find((s) => (Math.max(...vals) - Math.min(...vals)) / s <= 5) ?? 10000;
  const lo = Math.floor(Math.min(...vals) / step) * step, hi = Math.ceil(Math.max(...vals) / step) * step;
  const X = (i) => L + 14 + (i * (W - L - R - 28)) / (pts.length - 1), Y = (v) => T + ((hi - v) / (hi - lo || 1)) * (H - T - B);
  const band = [...pts.map((x, i) => `${X(i)},${Y(x.upper)}`), ...pts.map((x, i) => `${X(i)},${Y(x.lower)}`).reverse()].join(" ");
  const mi = pts.reduce((a, x, i) => (x.price < pts[a].price ? i : a), 0), ma = pts.reduce((a, x, i) => (x.price > pts[a].price ? i : a), 0);
  const idx = (iso) => pts.reduce((a, x, i) => (Math.abs(daysBetween(x.date, iso)) < Math.abs(daysBetween(pts[a].date, iso)) ? i : a), 0);
  const ticks = []; for (let v = lo; v <= hi; v += step) ticks.push(v);
  const monthsAt = pts.map((x, i) => [x, i]).filter(([x, i]) => i === 0 || x.date.slice(0, 7) !== pts[i - 1].date.slice(0, 7))
    .filter((_, n) => !narrow || n % 3 === 0);
  const inX = (x, w) => Math.min(Math.max(x, L + w / 2), W - R - w / 2); // 이름표가 그림 밖으로 잘리지 않게
  return (
    <section className="card">
      <div className="rc-ch"><h2>앞으로 12개월 예상 도매가</h2><small>원/kg · 전국 도매시장 · 예측은 최대 12개월</small></div>
      <svg className="rc-year" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="앞으로 12개월 예상 도매가">
        {harvest && (() => { const a = X(idx(harvest[0])), b = X(idx(harvest[1])); return (
          <g><rect x={a - 8} y={T - 22} width={Math.max(16, b - a + 16)} height={H - T - B + 22} rx="8" fill="rgba(246,224,176,.6)" />
            <text x={(a + b) / 2} y={T - 7} textAnchor="middle" fontSize="15" fontWeight="700" fill="#7a5a12">내 수확 기간</text></g>
        ); })()}
        {ticks.map((v) => <g key={v}><line x1={L} x2={W - R} y1={Y(v)} y2={Y(v)} stroke="rgba(19,38,26,.08)" /><text x={L - 10} y={Y(v) + 5} textAnchor="end" fontSize="15" fill="rgba(19,38,26,.8)">{won(v)}</text></g>)}
        {monthsAt.map(([x, i]) => <text key={x.date} x={X(i)} y={H - 8} textAnchor="middle" fontSize="15" fill="rgba(19,38,26,.8)">{i === 0 ? "지금" : `${mo(x.date)}월`}</text>)}
        <polygon points={band} fill="rgba(20,96,59,.1)" />
        <polyline points={pts.map((x, i) => `${X(i)},${Y(x.price)}`).join(" ")} fill="none" stroke="#e08a00" strokeWidth="3.5" strokeLinejoin="round" />
        <circle cx={X(0)} cy={Y(pts[0].price)} r="6" fill="#13261a" />
        <text x={inX(X(mi), 130)} y={Y(pts[mi].price) + 26} textAnchor="middle" fontSize="16" fontWeight="700" fill="#1d5fd8">최저 {won(pts[mi].price)}원</text>
        <text x={inX(X(ma), 130)} y={Y(pts[ma].price) - 14} textAnchor="middle" fontSize="16" fontWeight="700" fill="#d92d20">최고 {won(pts[ma].price)}원</text>
      </svg>
      <div className="rc-key"><span><i style={{ background: "#e08a00", height: 3 }} />{allNormal ? "평년 가격" : "AI 예상 가격"}</span><span><i style={{ background: "rgba(20,96,59,.25)" }} />{allNormal ? "평년 최저~최고" : "예측 범위"}</span>{harvest && <span><i style={{ background: "var(--amber)" }} />내 수확 기간</span>}</div>
      {note && <p className="rc-note">ⓘ {note}</p>}
    </section>
  );
}

function CropInfo({ crop, setCrop, form, rec, goLand }) {
  const list = useAsync(getRecommendCrops);
  const info = useAsync(() => getCropInfo(crop), [crop]);
  const c = list.data?.find((x) => x.code === crop);
  const ranks = useMemo(() => Object.fromEntries((rec?.results ?? []).slice(0, 3).map((r, i) => [r.crop, i + 1])), [rec]);
  const o = rec?.results?.find((r) => r.crop === crop);
  return (
    <>
      {list.data && <CropPicker list={list.data} crop={crop} ranks={ranks} onPick={setCrop} />}
      <Async state={info} minHeight={300}>
        {(d) => (
          <>
            <div className="rc-info-grid">
              <WhyCard crop={crop} cropName={c?.name ?? d.crop.name} emoji={c?.emoji ?? d.crop.emoji} rec={rec} form={form} info={d} goLand={goLand} />
              <Conditions info={d} />
            </div>
            <Calendar info={d} plantDate={o ? form.date : null} />
            {(!d.note || d.price_source === "forecast") && <PriceYear crop={crop} harvest={o ? [o.harvest_start, o.harvest_end] : null} />}
          </>
        )}
      </Async>
    </>
  );
}

export default function Recommend() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = ["info", "crop"].includes(params.get("tab")) ? "info" : "land";
  const crop = params.get("crop") || "onion";
  // 입력은 이 브라우저 탭 안에서만 기억 (작물 정보 화면이 이어받음)
  const [form, setForm] = useState(() => {
    try { return { ...DEFAULT_FORM, region: user?.region || DEFAULT_FORM.region, ...JSON.parse(sessionStorage.getItem("rc-form") || "{}"), date: todayIso() }; } catch { return DEFAULT_FORM; }
  });
  useEffect(() => { try { sessionStorage.setItem("rc-form", JSON.stringify(form)); } catch { /* 저장 못 해도 화면은 그대로 */ } }, [form]);
  const rec = useAsync(() => recommendCrops(request(form)), [JSON.stringify(form)]);
  const top = () => window.scrollTo({ top: 0, behavior: "smooth" });
  const goInfo = (c) => { setParams({ tab: "info", crop: c }); top(); };
  const goLand = () => { setParams({}); top(); };
  return (
    <div className="page">
      {tab === "land" ? (
        <>
          <div className="page-head"><h1>내 땅에 무엇을 심을까</h1><p>내 땅 조건과 심을 날짜를 알려 주시면, 임대료를 뺀 순수익이 높은 작물을 골라 드려요.</p></div>
          <LandForm key={JSON.stringify(form)} form={form} onApply={setForm} />
          <Results state={rec} form={form} goInfo={goInfo} retry={(date) => { setForm({ ...form, date }); top(); }} />
        </>
      ) : (
        <>
          <div className="page-head rc-head"><h1>작물 정보</h1><p>심는 때 · 재배 조건 · 앞으로 1년 가격을 한 번에 봐요.</p><button type="button" className="btn" onClick={goLand}>← 추천 결과로</button></div>
          <CropInfo crop={crop} setCrop={(c2) => setParams({ tab: "info", crop: c2 }, { replace: true })} form={form} rec={rec.data} goLand={goLand} />
        </>
      )}
    </div>
  );
}
