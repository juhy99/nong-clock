import { useState } from "react";
import CropSelect from "./CropSelect";
import { ITEMS50 } from "../mocks/items50";
import { addDays, daysBetween } from "../utils/format";

/**
 * 가격 예측 조건 (두 줄): ① 예측 날짜 + 빠른 버튼 ② 도매시장 → 부류 → 품목 → 품종 · 선택초기화 · [검색하기]
 * 도매시장을 먼저 고르면 그 시장에서 거래하는 품목만 부류·품목 목록에 남는다 (markets[].items)
 * value = { item, variety, market, date } — [검색하기] 를 눌러야 onSearch 로 넘어간다
 */
export default function PredictSearch({ value, markets, horizons, today, maxDays, onSearch }) {
  const [draft, setDraft] = useState(value);
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const national = markets.find((m) => m.code === "national");
  const bySido = markets.filter((m) => m.code !== "national").reduce((g, m) => ((g[m.sido] = g[m.sido] ?? []).push(m), g), {});
  const tradedIn = (code) => new Set((markets.find((m) => m.code === code)?.items ?? ITEMS50.map((i) => i.code)).filter((c) => ITEMS50.some((i) => i.code === c)));
  const only = tradedIn(draft.market);
  const pickMarket = (code) => {
    const ok = tradedIn(code);
    set(ok.has(draft.item) ? { market: code } : { market: code, item: ITEMS50.find((i) => ok.has(i.code)).code, variety: "" });
  };
  const reset = () => setDraft({ ...value, item: ITEMS50[0].code, variety: "", date: addDays(today, 30) });
  const horizon = daysBetween(today, draft.date);

  return (
    <section className="card ps">
      <div className="ps-row">
        <span className="ps-lb">예측 날짜</span>
        <input type="date" className="input ps-date" value={draft.date} min={addDays(today, 1)} max={addDays(today, maxDays)}
          onChange={(e) => e.target.value && set({ date: e.target.value })} aria-label="예측 날짜" />
        <div className="ps-chips">
          {horizons.map((h) => (
            <button key={h.days} type="button" className={`ps-chip ${horizon === h.days ? "on" : ""}`} onClick={() => set({ date: addDays(today, h.days) })}>{h.label} 후</button>
          ))}
        </div>
      </div>
      <div className="ps-row">
        <span className="ps-lb">품목</span>
        <label className="cs-f"><span>도매시장</span>
          <select className="input" value={draft.market} onChange={(e) => pickMarket(e.target.value)}>
            {national && <option value="national">{national.name}</option>}
            {Object.entries(bySido).map(([sido, ms]) => (
              <optgroup key={sido} label={sido}>{ms.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</optgroup>
            ))}
          </select>
        </label>
        <CropSelect item={draft.item} variety={draft.variety} onChange={set} only={only} warn />
        {only.size < ITEMS50.length && <span className="ps-note">이 시장에서 거래하지 않는 {ITEMS50.length - only.size}개 품목은 빠졌어요</span>}
        <span className="ps-actions">
          <button type="button" className="ps-reset" onClick={reset}>↻ 초기화</button>
          <button type="button" className="ps-go" onClick={() => onSearch(draft)}>검색하기</button>
        </span>
      </div>
    </section>
  );
}
