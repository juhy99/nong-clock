import { useState } from "react";
import CropSelect from "./CropSelect";
import { ITEMS50 } from "../mocks/items50";
import { addDays } from "../utils/format";

// 많이 찾는 품목 (바로 고르기)
const POPULAR = ["napa_cabbage", "onion", "green_onion", "apple", "garlic", "mandarin"];

/**
 * 가격 예측 조건 (v17, 11-11): 1. 도매시장 → 2. 부류 → 3. 품목 → 4. 품종 → 5. 기준 날짜 · [예측하기]
 * 기준 날짜 = 그날부터 4주를 예측 (오늘 ~ 1년 전). 도매시장을 먼저 고르면 그 시장에서 거래하는 품목만 남는다 (markets[].items)
 * value = { item, variety, market, date } — [예측하기] 를 눌러야 onSearch 로 넘어간다. 많이 찾는 품목 칩은 바로 넘어감
 */
export default function PredictSearch({ value, markets, today, onSearch }) {
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
  const popular = POPULAR.filter((c) => only.has(c)).map((c) => ITEMS50.find((i) => i.code === c));

  return (
    <section className="card pv-search">
      <div className="pv-fields">
        <label className="cs-f"><span>1. 도매시장</span>
          <select className="input" value={draft.market} onChange={(e) => pickMarket(e.target.value)}>
            {national && <option value="national">{national.name}</option>}
            {Object.entries(bySido).map(([sido, ms]) => (
              <optgroup key={sido} label={sido}>{ms.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</optgroup>
            ))}
          </select>
        </label>
        <CropSelect item={draft.item} variety={draft.variety} onChange={set} only={only} warn numbered />
        <label className="cs-f"><span>5. 기준 날짜</span>
          <input type="date" className="input" value={draft.date} min={addDays(today, -365)} max={today}
            onChange={(e) => e.target.value && set({ date: e.target.value })} />
        </label>
        <button type="button" className="btn primary pv-go" onClick={() => onSearch(draft)}>예측하기 →</button>
      </div>
      <div className="pv-pop">
        <span>많이 찾는 품목</span>
        {popular.map((i) => (
          <button key={i.code} type="button" className={`pill sm ${value.item === i.code && !value.variety ? "on" : ""}`}
            onClick={() => onSearch({ ...draft, item: i.code, variety: "" })}>{i.name}</button>
        ))}
        {only.size < ITEMS50.length && <span className="pv-note">이 시장에서 거래하지 않는 {ITEMS50.length - only.size}개 품목은 빠졌어요</span>}
      </div>
    </section>
  );
}
