import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getMarketCompare, getPriceHistory, getSupply, getTodayPrices } from "../api/market";
import { Async, PriceChange, SectionHead, useAsync } from "../components/common";
import ItemImage from "../components/ItemImage";
import { md, shortDate, won, wonPerKg } from "../utils/format";

const tipWon = (v) => wonPerKg(v);

function ItemCharts({ item, name, emoji }) {
  const hist = useAsync(() => getPriceHistory(item, 30), [item]);
  const mkt = useAsync(() => getMarketCompare(item), [item]);
  const sup = useAsync(() => getSupply(item), [item]);
  return (
    <>
      <div className="two-col">
        <section className="card">
          <SectionHead title={`${emoji} ${name} 가격 동향`} desc="최근 30 조사일 · 도매/소매 (원/kg)" />
          <Async state={hist} minHeight={260}>
            {(d) => (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={d.points}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="date" tickFormatter={md} fontSize={12} minTickGap={20} />
                  <YAxis fontSize={12} tickFormatter={won} width={56} />
                  <Tooltip formatter={tipWon} labelFormatter={shortDate} />
                  <Legend />
                  <Line name="도매" dataKey="wholesale" stroke="#1fa463" strokeWidth={2} dot={false} />
                  <Line name="소매" dataKey="retail" stroke="#e8a33d" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Async>
        </section>
        <section className="card">
          <SectionHead title="유통처별 가격 비교" desc="전국 주요 도매시장 · 산지공판장 (원/kg)" />
          <Async state={mkt} minHeight={260}>
            {(d) => (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={d.markets}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                  <XAxis dataKey="market" fontSize={12} />
                  <YAxis fontSize={12} tickFormatter={won} width={56} />
                  <Tooltip formatter={tipWon} />
                  <Bar name="가격" dataKey="price" fill="#1fa463" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Async>
        </section>
      </div>
      <section className="card">
        <SectionHead title="수급 동향 리포트" desc="월별 생산량(톤) vs 평년 · 이후 달은 전망치" />
        <Async state={sup} minHeight={260}>
          {(d) => (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={d.months.map((m) => ({ ...m, month: m.is_forecast ? `${m.month}(예상)` : m.month }))}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                  <XAxis dataKey="month" fontSize={12} />
                  <YAxis fontSize={12} width={48} />
                  <Tooltip formatter={(v) => `${won(v)}톤`} />
                  <Legend />
                  <Area name="생산량" dataKey="production" stroke="#1fa463" fill="#d8ecdf" />
                  <ReferenceLine y={d.months[0].normal} stroke="#d93025" strokeDasharray="5 5" label={{ value: "평년", fontSize: 12, fill: "#d93025", position: "insideTopRight" }} />
                </AreaChart>
              </ResponsiveContainer>
              <div className="banner info small" style={{ marginTop: 12 }}>📋 {d.note}</div>
            </>
          )}
        </Async>
      </section>
    </>
  );
}

export default function Market() {
  const [params, setParams] = useSearchParams();
  const [cat, setCat] = useState("전체");
  const [q, setQ] = useState("");
  const state = useAsync(getTodayPrices);
  const data = state.data;

  // 분류 탭은 품목 목록에서 만든다 → 품목이 바뀌어도 코드 수정 불필요
  const categories = useMemo(() => ["전체", ...new Set(data?.items.map((i) => i.category) ?? [])], [data]);
  const rows = (data?.items ?? []).filter((i) => (cat === "전체" || i.category === cat) && i.name.includes(q.trim()));
  const selectedCode = params.get("item") || data?.items[0]?.item;
  const selected = data?.items.find((i) => i.item === selectedCode) ?? data?.items[0];

  return (
    <div className="page">
      <div className="page-head">
        <h1>시세 · 수급 정보</h1>
        <p>모든 가격은 1kg 기준입니다. 품목을 선택하면 아래 그래프가 바뀝니다.</p>
      </div>
      <section className="card">
        <Async state={state} minHeight={300}>
          {(d) => (
            <>
              <div style={{ display: "flex", gap: 12, justifyContent: "space-between", flexWrap: "wrap", marginBottom: 14 }}>
                <div className="pills">
                  {categories.map((c) => (
                    <button key={c} className={`pill ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>{c}</button>
                  ))}
                </div>
                <input className="input" style={{ maxWidth: 220 }} placeholder="품목 검색" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <p className="muted small" style={{ margin: "0 0 8px" }}>
                {shortDate(d.base_date)} {d.market} 기준 · 전일 대비는 직전 조사일({shortDate(d.compared_date)}) 대비
              </p>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>품목</th>
                      <th>분류</th>
                      <th className="r">도매가 (원/kg)</th>
                      <th className="r">직전 조사일 대비</th>
                      <th className="r">소매가 (원/kg)</th>
                      <th className="r">유통마진</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((p) => (
                      <tr key={p.item} className={`clickable ${p.item === selected?.item ? "selected" : ""}`} onClick={() => setParams({ item: p.item })}>
                        <td><span className="item-cell"><ItemImage code={p.item} emoji={p.emoji} alt="" className="xs" /> <b>{p.name}</b></span></td>
                        <td className="muted">{p.category}</td>
                        <td className="r num"><b>{won(p.price)}</b></td>
                        <td className="r"><PriceChange change={p.change} changePct={p.change_pct} /></td>
                        <td className="r num">{won(p.retail_price)}</td>
                        <td className="r num muted">{p.margin_pct}%</td>
                      </tr>
                    ))}
                    {rows.length === 0 && (
                      <tr><td colSpan={6} className="state">검색 결과가 없습니다</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Async>
      </section>
      {selected && <ItemCharts item={selected.item} name={selected.name} emoji={selected.emoji} />}
    </div>
  );
}
