import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Area, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DEFAULT_GRADE, DEFAULT_MARKET, GRADES, getAuctionHouses, getGradePrices, getMarketShare, getMarkets, getOriginPrices, getPriceHistory, getTodayPrices, getVolumeTrend } from "../api/market";
import { Async, PriceChange, useAsync, useNarrow } from "../components/common";
import CropSelect from "../components/CropSelect";
import { varietyOf } from "../mocks/items50";
import { md, shortDate, todayIso, won, wonPerKg } from "../utils/format";
import "./market.css";

// 시세·수급: 날짜 · 시장 · 품목을 고르면 등급별 가격, 가격 추이, 출하지역, 반입 동향이 바뀐다.
// 처음 열면 전국 도매시장 · 상 등급. 소매가는 전국 소매가 하나뿐이라 등급을 바꿔도 같다.
const QUICK_MARKETS = ["national", "110001", "210001", "220001"]; // 전국 · 서울가락 · 부산엄궁 · 대구북부
const gradeName = (code) => GRADES.find((g) => g.code === code)?.name ?? code;
const tipWon = (v) => (v == null ? "거래 없음" : wonPerKg(v));

/** 5거래일 작은 그래프: 평균선 위는 빨강, 아래는 파랑 */
function Spark({ points, id }) {
  const W = 200, H = 56;
  const vals = points.map((p) => p.price).filter((v) => v != null);
  if (vals.length < 2) return <svg className="spark" viewBox={`0 0 ${W} ${H}`}><line x1="0" x2={W} y1={H / 2} y2={H / 2} className="spark-base" /></svg>;
  const mn = Math.min(...vals), mx = Math.max(...vals), avg = vals.reduce((a, b) => a + b) / vals.length;
  const x = (i) => (W * i) / (points.length - 1), y = (v) => 5 + (H - 10) * (1 - (v - mn) / (mx - mn || 1));
  const pts = points.map((p, i) => [i, p.price]).filter(([, v]) => v != null);
  let d = `M${x(pts[0][0])},${y(pts[0][1])}`;
  for (let k = 1; k < pts.length; k++) {
    const [i0, v0] = pts[k - 1], [i1, v1] = pts[k], cx = (x(i0) + x(i1)) / 2;
    d += ` C${cx},${y(v0)} ${cx},${y(v1)} ${x(i1)},${y(v1)}`;
  }
  const by = y(avg), area = `${d} L${x(pts.at(-1)[0])},${by} L${x(pts[0][0])},${by} Z`;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <defs>
        <clipPath id={`up-${id}`}><rect x="0" y="0" width={W} height={by} /></clipPath>
        <clipPath id={`dn-${id}`}><rect x="0" y={by} width={W} height={H} /></clipPath>
      </defs>
      <path d={area} fill="#fde3e1" clipPath={`url(#up-${id})`} />
      <path d={area} fill="#e3ecfd" clipPath={`url(#dn-${id})`} />
      <line x1="0" x2={W} y1={by} y2={by} className="spark-base" />
      <path d={d} fill="none" stroke="var(--up)" strokeWidth="2" clipPath={`url(#up-${id})`} vectorEffect="non-scaling-stroke" />
      <path d={d} fill="none" stroke="var(--down)" strokeWidth="2" clipPath={`url(#dn-${id})`} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function YearAgo({ value }) {
  if (value == null) return <span className="muted">-</span>;
  return <b className={value > 0 ? "up" : value < 0 ? "down" : "flat"}>{value > 0 ? "▲" : value < 0 ? "▼" : "-"} {Math.abs(value).toFixed(0)}%</b>;
}

function GradeCard({ title, tag, card, kind, onClick, dates }) {
  const empty = card.price == null;
  return (
    <button type="button" className={`grade-card ${kind ?? ""} ${empty ? "empty" : ""}`} onClick={onClick} disabled={!onClick}>
      <div className="t"><b>{title}</b>{tag && <span className="tag">{tag}</span>}</div>
      {empty ? (
        <>
          <div className="p">-</div>
          <div className="none">이 날은 {title} 등급 거래가 없어요</div>
        </>
      ) : (
        <>
          <div className="p num">{won(card.price)}<small>원/kg</small></div>
          <div className="d"><span>전일</span>{card.change == null ? <span className="muted">-</span> : <PriceChange change={card.change} changePct={card.change_pct} />}</div>
          <div className="d"><span>전년</span><YearAgo value={card.year_ago_pct} /></div>
        </>
      )}
      <Spark points={card.points} id={`${kind ?? ""}${title}`} />
      <div className="ax"><span>5거래일 전</span><span>{md(dates.at(-1))}</span></div>
    </button>
  );
}

/** 최근 30일 거래일의 절반 미만인 등급은 숨김 (시장마다 등급을 붙이는 방식이 달라, 예: 부산엄궁 양배추는 특·보통만). 평균과 지금 고른 등급은 늘 보임 */
export const shownGrades = (d, grade) =>
  d.grades.filter((g) => g.grade === "ALL" || g.grade === grade || g.days_30 == null || d.days_30 == null || g.days_30 * 2 >= d.days_30);

function GradeSection({ item, market, date, grade, setGrade, defGrade, onAvail }) {
  const state = useAsync(() => getGradePrices(item, { market, date }), [item, market, date]);
  const avail = state.data ? shownGrades(state.data, grade).map((g) => g.grade).join(",") : "";
  useEffect(() => { onAvail?.(avail); }, [avail, onAvail]);
  return (
    <Async state={state} minHeight={220}>
      {(d) => {
        const dates = d.retail.points.map((p) => p.date);
        const shown = shownGrades(d, grade);
        const hidden = d.grades.filter((g) => !shown.includes(g)).map((g) => gradeName(g.grade));
        return (
          <>
            <div className="grade-grid">
              {shown.map((g) => (
                <GradeCard key={g.grade} title={gradeName(g.grade)} tag={g.grade === defGrade ? "기본" : g.grade === "ALL" ? "거래량 반영" : null}
                  card={g} kind={g.grade === grade ? "on" : ""} onClick={() => setGrade(g.grade)} dates={dates} />
              ))}
              <GradeCard title="소매가" tag="등급 무관" card={d.retail} kind="retail" dates={dates} />
            </div>
            <p className="hint" style={{ margin: "10px 0 0" }}>
              카드를 누르면 아래 가격 추이가 그 등급으로 바뀌어요.
              {hidden.length > 0 && ` 이 시장은 최근 30일 ${hidden.join("·")} 등급 거래가 거의 없어 숨겼어요.`}
            </p>
          </>
        );
      }}
    </Async>
  );
}

function TrendCard({ item, market, date, grade, setGrade, avail }) {
  const [days, setDays] = useState(8);
  const [more, setMore] = useState(false);
  const state = useAsync(() => getPriceHistory(item, { market, grade, date, days }), [item, market, grade, date, days]);
  return (
    <section className="card mk-flex">
      <div className="mk-card-head">
        <h3>가격 추이</h3>
        <div className="seg">
          {GRADES.filter((g) => !avail || avail.split(",").includes(g.code)).map((g) => <button key={g.code} className={grade === g.code ? "on" : ""} onClick={() => setGrade(g.code)}>{g.name}</button>)}
        </div>
        <select className="input mk-days" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="기간">
          <option value={8}>최근 8일</option>
          <option value={15}>최근 15일</option>
          <option value={30}>최근 30일</option>
        </select>
      </div>
      <Async state={state} minHeight={260}>
        {(d) => {
          const rows = [...d.points].reverse();
          return (
            <>
              <div className="mk-grow"><ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={d.points} margin={{ top: 18, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                  <XAxis dataKey="date" tickFormatter={md} fontSize={12} minTickGap={16} />
                  <YAxis fontSize={12} tickFormatter={won} width={56} domain={["auto", "auto"]} />
                  <Tooltip formatter={tipWon} labelFormatter={shortDate} />
                  <Area name={`도매 ${gradeName(grade)}`} dataKey="price" stroke="#1fa463" strokeWidth={2.4} fill="#e8f6ee" dot={{ r: 3 }} connectNulls={false} />
                  <Line name="소매가 (등급 무관)" dataKey="retail" stroke="#b8a06a" strokeWidth={2} strokeDasharray="6 4" dot={false} />
                </ComposedChart>
              </ResponsiveContainer></div>
              <div className="mk-legend"><span className="l-w">도매 {gradeName(grade)}</span><span className="l-r">소매가 (등급 무관)</span></div>
              <div className="table-wrap">
                <table className="table mk-table">
                  <thead>
                    <tr><th>날짜</th><th className="r">가격 (원/kg)</th><th className="r">전일 대비</th><th className="r">최고</th><th className="r">최저</th><th className="r">반입량</th><th className="r">소매가</th></tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, more ? rows.length : 3).map((p, i) => (
                      <tr key={p.date} className={i === 0 ? "hl" : ""}>
                        <td>{shortDate(p.date)}</td>
                        <td className="r num"><b>{won(p.price)}</b></td>
                        <td className="r">{p.change == null ? <span className="muted">-</span> : <PriceChange change={p.change} changePct={p.change_pct} />}</td>
                        <td className="r num">{won(p.high)}</td>
                        <td className="r num">{won(p.low)}</td>
                        <td className="r num vol">{won(p.volume_t)}톤</td>
                        <td className="r num retail">{won(p.retail)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > 3 && <button className="btn ghost sm mk-more" onClick={() => setMore(!more)}>{more ? "접기" : `더 많은 날짜 보기 (${rows.length}일)`}</button>}
            </>
          );
        }}
      </Async>
    </section>
  );
}

function OriginCard({ item, market, date }) {
  const [view, setView] = useState("price");
  const [page, setPage] = useState(0);
  const state = useAsync(() => getOriginPrices(item, { market, date }), [item, market, date]);
  const key = view === "price" ? "price" : "volume_t";
  return (
    <section className="card">
      <div className="mk-card-head">
        <h3>출하지역별 가격</h3>
        <div className="seg">
          <button className={view === "price" ? "on" : ""} onClick={() => setView("price")}>가격</button>
          <button className={view === "volume" ? "on" : ""} onClick={() => setView("volume")}>반입량</button>
        </div>
      </div>
      <Async state={state} minHeight={260} empty="이 날은 출하지역 자료가 없어요">
        {(d) => {
          const pages = Math.ceil(d.regions.length / 4);
          const cur = Math.min(page, pages - 1);
          return (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={d.regions} margin={{ top: 18, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                  <XAxis dataKey="region" fontSize={12} />
                  <YAxis fontSize={12} tickFormatter={won} width={56} />
                  <Tooltip formatter={(v) => (view === "price" ? wonPerKg(v) : `${won(v)}톤`)} />
                  <Bar name={view === "price" ? "평균 가격" : "반입량"} dataKey={key} fill="#57c98a" radius={[8, 8, 0, 0]} maxBarSize={36}
                    label={{ position: "top", fontSize: 12, fill: "#1b1f1c", formatter: won }} />
                </BarChart>
              </ResponsiveContainer>
              <div className="table-wrap">
                <table className="table mk-table">
                  <thead>
                    <tr><th>출하지역</th><th className="r">평균 가격 (원/kg)</th><th className="r">전일 대비</th><th className="r">최고</th><th className="r">최저</th><th className="r">반입량</th></tr>
                  </thead>
                  <tbody>
                    {d.regions.slice(cur * 4, cur * 4 + 4).map((r) => (
                      <tr key={r.region}>
                        <td>{r.region}</td>
                        <td className="r num"><b>{won(r.price)}</b></td>
                        <td className="r"><PriceChange change={r.change} changePct={r.change_pct} /></td>
                        <td className="r num">{won(r.high)}</td>
                        <td className="r num">{won(r.low)}</td>
                        <td className="r num vol">{won(r.volume_t)}톤</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {pages > 1 && (
                <div className="mk-pager">
                  <button className="btn ghost sm" disabled={cur === 0} onClick={() => setPage(cur - 1)}>‹</button>
                  <span className="muted small">{cur + 1} / {pages}</span>
                  <button className="btn ghost sm" disabled={cur === pages - 1} onClick={() => setPage(cur + 1)}>›</button>
                </div>
              )}
              <p className="hint" style={{ margin: "8px 0 0" }}>출하지역은 시·도 단위, 가격은 등급 평균이에요.</p>
            </>
          );
        }}
      </Async>
    </section>
  );
}

function Ring({ pct, color }) {
  const r = 32, C = 2 * Math.PI * r;
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" aria-hidden="true">
      <circle cx="40" cy="40" r={r} fill="none" stroke="#eef1ec" strokeWidth="8" />
      <circle cx="40" cy="40" r={r} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" strokeDasharray={`${(C * pct) / 100} ${C}`} transform="rotate(-90 40 40)" />
      <text x="40" y="45" textAnchor="middle" fontSize="15" fontWeight="800" fill="var(--text)">{pct}%</text>
    </svg>
  );
}

function VolumeSection({ item, itemName, market, date }) {
  const [more, setMore] = useState(false);
  const state = useAsync(() => getVolumeTrend(item, { market, date }), [item, market, date]);
  return (
    <Async state={state} minHeight={300}>
      {(d) => {
        const s = d.summary;
        const rows = [...d.periods].reverse();
        const data = d.periods.map((p) => ({ period: p.period, top1: p.top1.volume_t, top2: p.top2.volume_t, others: p.others_t, total: p.total_t, r1: p.top1.region, r2: p.top2.region }));
        return (
          <div className="mk-volume">
            <section className="card">
              <div className="mk-card-head">
                <h3>출하지역별 반입량 (톤)</h3>
                <div className="mk-legend" style={{ margin: 0 }}><span className="l-1">1위</span><span className="l-2">2위</span><span className="l-3">기타</span></div>
              </div>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={data} margin={{ top: 18, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                  <XAxis dataKey="period" fontSize={11} interval="preserveStartEnd" minTickGap={6} />
                  <YAxis fontSize={12} tickFormatter={won} width={56} />
                  <Tooltip formatter={(v, name, p) => [`${won(v)}톤`, name === "1위" ? `1위 ${p.payload.r1}` : name === "2위" ? `2위 ${p.payload.r2}` : name]} />
                  <Bar name="1위" dataKey="top1" stackId="v" fill="#0e7a45" maxBarSize={32} />
                  <Bar name="2위" dataKey="top2" stackId="v" fill="#57c98a" maxBarSize={32} />
                  <Bar name="기타" dataKey="others" stackId="v" fill="#d9e9c2" maxBarSize={32} radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="table-wrap">
                <table className="table mk-table">
                  <thead><tr><th>기간</th><th className="r">1위</th><th className="r">2위</th><th className="r">기타</th><th className="r">총 반입량</th></tr></thead>
                  <tbody>
                    {rows.slice(0, more ? rows.length : 3).map((p, i) => (
                      <tr key={p.start} className={i === 0 ? "hl" : ""}>
                        <td>{p.period}</td>
                        <td className="r">{p.top1.region} {won(p.top1.volume_t)}톤</td>
                        <td className="r">{p.top2.region} {won(p.top2.volume_t)}톤</td>
                        <td className="r num">{won(p.others_t)}톤</td>
                        <td className="r num vol">{won(p.total_t)}톤</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {rows.length > 3 && <button className="btn ghost sm mk-more" onClick={() => setMore(!more)}>{more ? "접기" : `더 많은 기간 보기 (${rows.length}순)`}</button>}
            </section>
            <section className="mk-sum">
              <div className="muted">{s.period} 기준</div>
              <div className="big">{itemName} 주요 출하 지역은<br /><em>{s.top[0].region}, {s.top[1].region}</em>예요</div>
              <div className="rings">
                {s.top.map((t, i) => (
                  <div key={t.region} className="ring">
                    <Ring pct={t.share_pct} color={i === 0 ? "#0e7a45" : "#57c98a"} />
                    <b>{t.region}</b>
                    <div className="num v">{won(t.volume_t)}톤</div>
                    <div className="muted small">전년 같은 순 <YearAgo value={t.year_ago_pct} /></div>
                  </div>
                ))}
                <div className="ring">
                  <Ring pct={Math.max(0, 100 - s.top[0].share_pct - s.top[1].share_pct)} color="#b9d39a" />
                  <b>기타</b>
                  <div className="num v">{won(s.others_t)}톤</div>
                </div>
              </div>
              <div className="total">
                총 반입량 <b className="num">{won(s.total_t)}톤</b> · 지난 순 같은 기간보다 {s.change_t >= 0 ? "+" : "-"}{won(Math.abs(s.change_t))}톤{" "}
                <YearAgo value={s.change_pct} />
              </div>
              <details className="more-info"><summary>반입량은 어떻게 셌나요?</summary>순(10일)마다 더한 값이에요. 이번 순은 고른 날짜까지라서, 지난 순도 같은 거래일 수만큼만 더해 비교해요.</details>
            </section>
          </div>
        );
      }}
    </Async>
  );
}

/* ── 도매시장 · 산지 (11-12 샘플): 고른 시장과 상관없이 품목·품종만, 최근 12달 ──
   출하지역별 가격 카드처럼: 위 막대그래프(가격/몫 바꿔 보기) + 아래 표 4줄씩 넘김 */
function SampleTag({ sample }) {
  return <span className={`mk-tag ${sample ? "ex" : ""}`}>{sample ? "예시 데이터" : "실제"}</span>;
}
const PER = 4;
function Pager({ page, pages, setPage }) {
  if (pages <= 1) return null;
  return (
    <div className="mk-pager">
      <button className="btn ghost sm" disabled={page === 0} onClick={() => setPage(page - 1)}>‹</button>
      <span className="muted small">{page + 1} / {pages}</span>
      <button className="btn ghost sm" disabled={page === pages - 1} onClick={() => setPage(page + 1)}>›</button>
    </div>
  );
}
const C_HI = "#0e7a45", C_MID = "#57c98a", C_LO = "#bfe3cc", C_PAST = "#cfd8cf";

function MarketShareCard({ item }) {
  const [view, setView] = useState("price");
  const [page, setPage] = useState(0);
  const state = useAsync(() => getMarketShare(item), [item]);
  const narrow = useNarrow(); // 휴대폰은 그래프에 4곳만 (이름이 겹치지 않게)
  return (
    <section className="card mk-flex">
      <div className="mk-card-head">
        <h3>도매시장별 가격</h3>
        <div className="seg">
          <button className={view === "price" ? "on" : ""} onClick={() => setView("price")}>가격</button>
          <button className={view === "share" ? "on" : ""} onClick={() => setView("share")}>물량 몫</button>
        </div>
        {state.data && <SampleTag sample={state.data.sample} />}
      </div>
      <Async state={state} minHeight={300}>
        {(d) => {
          const prices = d.markets.map((m) => m.price);
          const hi = Math.max(...prices), lo = Math.min(...prices);
          const color = (m) => (view === "share" ? C_MID : m.price === hi ? C_HI : m.price === lo ? C_LO : C_MID);
          const pages = Math.ceil(d.markets.length / PER), cur = Math.min(page, pages - 1);
          return (
            <>
              <div className="mk-grow">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={narrow ? d.markets.slice(0, 4) : d.markets} margin={{ top: 22, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                    <XAxis dataKey="market" fontSize={12} interval={0} />
                    <YAxis fontSize={12} tickFormatter={view === "price" ? won : (v) => `${v}%`} width={56} />
                    <Tooltip formatter={(v) => (view === "price" ? wonPerKg(v) : `${v}%`)} />
                    {view === "price" && <ReferenceLine y={d.weighted_avg} stroke="#13261a" strokeDasharray="5 4" />}
                    <Bar name={view === "price" ? "평균 경락가" : "물량 몫"} dataKey={view === "price" ? "price" : "share_pct"} radius={[8, 8, 0, 0]} maxBarSize={36}
                      label={{ position: "top", fontSize: narrow ? 11 : 12, fill: "#1b1f1c", formatter: view === "price" ? won : (v) => `${v}%` }}>
                      {(narrow ? d.markets.slice(0, 4) : d.markets).map((m) => <Cell key={m.code} fill={color(m)} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mk-key"><span><i style={{ background: C_HI }} />가장 비쌈</span><span><i style={{ background: C_LO }} />가장 쌈</span><span><i className="dash" />물량 가중 평균 {won(d.weighted_avg)}원</span></div>
              <div className="table-wrap mk-nomask">
                <table className="table mk-table mk-ms">
                  <thead><tr><th>도매시장</th><th className="r">평균 가격 (원/kg)</th><th className="r">평균 대비</th><th className="r">물량 몫</th></tr></thead>
                  <tbody>
                    {d.markets.slice(cur * PER, cur * PER + PER).map((m) => {
                      const diff = Math.round(((m.price - d.weighted_avg) / d.weighted_avg) * 1000) / 10;
                      return (
                        <tr key={m.code}>
                          <td>{m.market}</td>
                          <td className="r num"><b>{won(m.price)}</b></td>
                          <td className={`r num ${diff > 0 ? "up" : diff < 0 ? "down" : ""}`}>{diff > 0 ? "▲" : diff < 0 ? "▼" : ""} {Math.abs(diff)}%</td>
                          <td className="r num vol">{m.share_pct}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pager page={cur} pages={pages} setPage={setPage} />
              <p className="mk-src">물량 많은 시장 {d.markets.length}곳 (전체 {d.market_count}곳) · 최근 12달 평균 경락가 · 자료: 공영도매시장 경매원장</p>
            </>
          );
        }}
      </Async>
    </section>
  );
}

function AuctionHouseCard({ item }) {
  const [view, setView] = useState("price");
  const [page, setPage] = useState(0);
  const state = useAsync(() => getAuctionHouses(item), [item]);
  const narrow = useNarrow();
  return (
    <section className="card mk-flex">
      <div className="mk-card-head">
        <h3>산지공판장 가격</h3>
        <div className="seg">
          <button className={view === "price" ? "on" : ""} onClick={() => setView("price")}>가격</button>
          <button className={view === "share" ? "on" : ""} onClick={() => setView("share")}>물량 몫</button>
        </div>
        {state.data && <SampleTag sample={state.data.sample} />}
      </div>
      <Async state={state} minHeight={300}>
        {(d) => {
          const pages = Math.ceil(d.houses.length / PER), cur = Math.min(page, pages - 1);
          return (
            <>
              <div className="mk-grow">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={narrow ? d.houses.slice(0, 4) : d.houses} margin={{ top: 22, right: 8, left: 0, bottom: 0 }} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                    <XAxis dataKey="short" fontSize={12} interval={0} />
                    <YAxis fontSize={12} tickFormatter={view === "price" ? won : (v) => `${v}%`} width={56} />
                    <Tooltip formatter={(v) => (view === "price" ? wonPerKg(v) : `${v}%`)} labelFormatter={(l) => d.houses.find((h) => h.short === l)?.name ?? l} />
                    {view === "price" ? (
                      <>
                        <Bar name={d.past} dataKey="past_price" fill={C_PAST} radius={[6, 6, 0, 0]} maxBarSize={22} />
                        <Bar name={d.period} dataKey="price" fill={C_HI} radius={[6, 6, 0, 0]} maxBarSize={22}
                          label={narrow ? false : { position: "top", fontSize: 11, fill: "#1b1f1c", formatter: won }} />
                      </>
                    ) : (
                      <Bar name="물량 몫" dataKey="share_pct" fill={C_MID} radius={[8, 8, 0, 0]} maxBarSize={36}
                        label={{ position: "top", fontSize: 12, fill: "#1b1f1c", formatter: (v) => `${v}%` }} />
                    )}
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {view === "price" && <div className="mk-key"><span><i style={{ background: C_HI }} />{d.period}</span><span><i style={{ background: C_PAST }} />{d.past} 평균</span></div>}
              <div className="table-wrap mk-nomask">
                <table className="table mk-table mk-ah">
                  <thead><tr><th>공판장</th><th>시·도</th><th className="r">{d.period}</th><th className="r">{d.past} 대비</th><th className="r">물량 몫</th></tr></thead>
                  <tbody>
                    {d.houses.slice(cur * PER, cur * PER + PER).map((h) => {
                      const diff = Math.round(((h.price - h.past_price) / h.past_price) * 1000) / 10;
                      return (
                        <tr key={h.name}>
                          <td>{h.name}<small className="sd">{h.sido}</small></td>
                          <td>{h.sido}</td>
                          <td className="r num"><b>{won(h.price)}</b></td>
                          <td className={`r num ${diff > 0 ? "up" : diff < 0 ? "down" : ""}`}>{diff > 0 ? "▲" : diff < 0 ? "▼" : ""} {Math.abs(diff)}%</td>
                          <td className="r num vol">{h.share_pct}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Pager page={cur} pages={pages} setPage={setPage} />
              <p className="mk-src">물량 많은 공판장 {d.houses.length}곳 · 최근 12달 평균 경락가 · 자료: aT 산지공판장 경락 자료</p>
            </>
          );
        }}
      </Async>
    </section>
  );
}

export default function Market() {
  const [params, setParams] = useSearchParams();
  const today = useAsync(getTodayPrices);
  const markets = useAsync(getMarkets);
  const items = today.data?.items ?? [];
  const item = params.get("item") || items[0]?.item;
  const vInfo = varietyOf(item, params.get("variety"));
  const variety = vInfo ? vInfo.id : ""; // 없어진 품종 id(옛 주소)는 전체로
  const itemName = (items.find((i) => i.item === item)?.name ?? "") + (vInfo ? ` ${vInfo.label}` : "");
  const key = variety ? `${item}~${variety}` : item; // [샘플] 품종은 "품목~품종" 으로 넘긴다 (api/market.js)
  const market = params.get("market") || DEFAULT_MARKET;
  const date = params.get("date") || "";
  const defGrade = market === "national" ? DEFAULT_GRADE : "ALL"; // 시장을 고르면 기본은 평균 (시장마다 쓰는 등급이 달라 상 등급이 빈 곳이 많음)
  const grade = params.get("grade") || defGrade;
  const [avail, setAvail] = useState("");
  const marketInfo = markets.data?.find((m) => m.code === market);
  const marketName = marketInfo?.name ?? "";
  // 그 시장에서 거래하지 않는 품목이면 아래 정보 대신 안내 (예: 안동은 버섯류·무·대파 거래 기록 없음)
  const notTraded = marketInfo?.items && item && !marketInfo.items.includes(item);

  // 주소(?item=&market=&date=&grade=)에 조건을 담아 새로고침·공유해도 같은 화면이 나온다. 기본값은 주소에서 뺀다.
  const set = (key, value, fallback) => {
    const next = new URLSearchParams(params);
    if (!value || value === fallback) next.delete(key);
    else next.set(key, value);
    setParams(next, { replace: true });
  };
  // 시장을 바꾸면 등급은 그 시장 기본(전국=상, 시장=평균)으로 되돌림 (시장마다 쓰는 등급이 달라서)
  const pickMarket = (code) => {
    const next = new URLSearchParams(params);
    if (!code || code === DEFAULT_MARKET) next.delete("market");
    else next.set("market", code);
    next.delete("grade");
    setParams(next, { replace: true });
  };

  return (
    <div className="page">
      <div className="page-head mk-head">
        <div>
          <h1>시세 · 수급</h1>
          <p>도매시장 경락가 · 1kg 기준</p>
        </div>
        {item && <Link className="btn sm mk-ai" to={`/ai?item=${item}${variety ? `&variety=${variety}` : ""}`}>{itemName} AI 가격 예측 보기 →</Link>}
      </div>

      <section className="mk-filter">
        <div className="f">
          <label htmlFor="mk-date">날짜</label>
          <input id="mk-date" type="date" className="input" max={todayIso()} value={date || today.data?.base_date || ""} onChange={(e) => set("date", e.target.value)} />
          <div className="pills">
            <button className={`pill sm ${date ? "" : "on"}`} onClick={() => set("date", "")}>최근 거래일</button>
          </div>
        </div>
        <div className="f">
          <label htmlFor="mk-market">시장</label>
          <select id="mk-market" className="input" value={market} onChange={(e) => pickMarket(e.target.value)}>
            {(markets.data ?? []).map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}
          </select>
          <div className="pills">
            {QUICK_MARKETS.map((code) => {
              const m = markets.data?.find((x) => x.code === code);
              return m && <button key={code} className={`pill sm ${market === code ? "on" : ""}`} onClick={() => pickMarket(code)}>{code === "national" ? "전국 평균" : m.name}</button>;
            })}
          </div>
        </div>
        <div className="f mk-crop">
          <label>품목 · 품종</label>
          <CropSelect item={item} variety={variety} only={new Set(items.map((i) => i.item))} onChange={(v) => {
            const next = new URLSearchParams(params);
            next.set("item", v.item);
            if (v.variety) next.set("variety", v.variety); else next.delete("variety");
            setParams(next, { replace: true });
          }} />
        </div>
      </section>

      {notTraded && (
        <section className="card state">
          <p style={{ margin: "0 0 12px" }}>{marketName} 도매시장은 최근 1년 동안 {itemName} 거래 기록이 없어요. 다른 품목을 골라 보세요.</p>
          <div className="pills" style={{ justifyContent: "center" }}>
            {items.filter((i) => marketInfo.items.includes(i.item)).map((i) => (
              <button key={i.item} className="pill sm" onClick={() => set("item", i.item)}>{i.name}</button>
            ))}
          </div>
        </section>
      )}
      {item && !notTraded && (
        <>
          <div className="mk-group">
            <div className="mk-sec"><h2>등급별 가격 한눈에 보기</h2><span>{marketName} · {itemName}</span></div>
            {variety && market !== "national" && (
              <p className="hint" style={{ margin: "0 0 10px" }}>품종별 시세는 전국 평균만 있어요. {marketName} 시세는 {items.find((i) => i.item === item)?.name ?? ""} 전체 값이에요.</p>
            )}
            <GradeSection item={key} market={market} date={date} grade={grade} setGrade={(g) => set("grade", g, defGrade)} defGrade={defGrade} onAvail={setAvail} />
          </div>
          <div className="mk-group">
            <div className="mk-sec"><h2>자세한 가격 정보</h2><span>{marketName} · {itemName}</span></div>
            <div className="two-col">
              <TrendCard item={key} market={market} date={date} grade={grade} setGrade={(g) => set("grade", g, defGrade)} avail={avail} />
              <OriginCard key={`${key}|${market}|${date}`} item={key} market={market} date={date} />
            </div>
          </div>
          <div className="mk-group">
            <div className="mk-sec"><h2>반입 동향</h2><span>{marketName} · {itemName}</span></div>
            <VolumeSection item={key} itemName={itemName} market={market} date={date} />
          </div>
          <div className="mk-group">
            <div className="mk-sec"><h2>도매시장 · 산지</h2><span>{itemName}</span></div>
            <div className="two-col mk-eq">
              <MarketShareCard item={key} />
              <AuctionHouseCard item={key} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
