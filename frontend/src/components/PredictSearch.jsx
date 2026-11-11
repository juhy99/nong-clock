import { useState } from "react";
import CropSelect from "./CropSelect";
import { ITEMS50 } from "../mocks/items50";
import { addDays } from "../utils/format";

// 예측 날짜 빠른 버튼 (오늘부터)
export const QUICK = [["1주", 7], ["1개월", 30], ["6개월", 182], ["1년", 365]];

/** 시·도 목록: 전국(평균) + 도매시장이 있는 시·도 (세종·제주는 공영도매시장이 없어 빠짐) */
export function regionsOf(markets) {
  const sido = [...new Set(markets.filter((m) => m.code !== "national").map((m) => m.sido))];
  return [{ code: "national", name: "전국 (평균)" }, ...sido.map((s) => ({ code: s, name: s }))];
}
/** 지역 안 도매시장 중 이 품목을 거래하는 곳 (전국 = 전국 평균 하나) */
export function marketsIn(markets, region, item) {
  if (region === "national") return markets.filter((m) => m.code === "national");
  return markets.filter((m) => m.sido === region && (!item || (m.items ?? []).includes(item)));
}

/**
 * [샘플 11-11] 가격 예측 조건: 1. 지역(시·도) → 2. 부류 → 3. 품목 → 4. 품종 → 5. 예측 날짜(내일 ~ 1년 뒤) · [예측하기]
 * 지역을 고르면 그 안 도매시장마다 선을 그린다 (예: 서울 = 서울가락 · 서울강서). 지역에서 거래하지 않는 품목은 목록에서 빠짐
 * value = { region, item, variety, to } — [예측하기] 를 눌러야 onSearch. 예측 날짜 아래 빠른 버튼(1주·1개월·6개월·1년)은 바로 넘어감
 */
export default function PredictSearch({ value, markets, today, onSearch }) {
  const [draft, setDraft] = useState(value);
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const regions = regionsOf(markets);
  const tradedIn = (region) => {
    const ms = marketsIn(markets, region);
    const codes = region === "national" ? ITEMS50.map((i) => i.code) : ms.flatMap((m) => m.items ?? []);
    return new Set(codes.filter((c) => ITEMS50.some((i) => i.code === c)));
  };
  const only = tradedIn(draft.region);
  const pickRegion = (region) => {
    const ok = tradedIn(region);
    set(ok.has(draft.item) ? { region } : { region, item: ITEMS50.find((i) => ok.has(i.code)).code, variety: "" });
  };
  const n = (k) => marketsIn(markets, k, draft.item).length;

  return (
    <section className="card pv-search">
      <div className="pv-fields">
        <label className="cs-f"><span>1. 지역</span>
          <select className="input" value={draft.region} onChange={(e) => pickRegion(e.target.value)}>
            {regions.map((r) => <option key={r.code} value={r.code}>{r.name}{r.code !== "national" ? ` (${n(r.code)}곳)` : ""}</option>)}
          </select>
        </label>
        <CropSelect item={draft.item} variety={draft.variety} onChange={set} only={only} warn numbered />
        <label className="cs-f"><span>5. 예측 날짜</span>
          <input type="date" className="input" value={draft.to} min={addDays(today, 1)} max={addDays(today, 365)}
            onChange={(e) => e.target.value && set({ to: e.target.value })} />
        </label>
        <button type="button" className="btn primary pv-go" onClick={() => onSearch(draft)}>예측하기 →</button>
        {/* 예측 날짜 바로 아래, 날짜 칸과 같은 폭을 4칸으로: 오늘부터 1주 · 1개월 · 6개월 · 1년 */}
        <div className="pv-quick" role="group" aria-label="예측 날짜 빠르게 고르기 (오늘부터)">
          {QUICK.map(([label, days]) => (
            <button key={label} type="button" className={`pill sm ${draft.to === addDays(today, days) ? "on" : ""}`}
              onClick={() => onSearch({ ...draft, to: addDays(today, days) })}>{label}</button>
          ))}
        </div>
      </div>
    </section>
  );
}
