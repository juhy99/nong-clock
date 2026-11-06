import { useState } from "react";
import { useAuth } from "./AuthContext";
import CropSelect from "./CropSelect";
import { ITEMS50, itemOf } from "../mocks/items50";
import { addDays, daysBetween, shortDate } from "../utils/format";

// 최근 검색은 로그인한 사람만, 사람마다 따로 (이 브라우저에만 저장. 나중에 회원 API 로 옮길 수 있음)
const keyOf = (user) => `farmbid.predict.recent.${user.id}`;
const loadRecent = (user) => { if (!user) return []; try { return JSON.parse(localStorage.getItem(keyOf(user))) ?? []; } catch { return []; } };
const saveRecent = (user, v) => { try { localStorage.setItem(keyOf(user), JSON.stringify(v)); } catch { /* 저장 안 돼도 괜찮음 */ } };

/**
 * 가격 예측 조건: 예측 날짜 · 부류 → 품목 → 품종 · 도매시장 · (로그인 시) 최근 검색
 * value = { item, variety, market, date } — [검색하기] 를 눌러야 onSearch 로 넘어간다
 */
export default function PredictSearch({ value, markets, horizons, today, maxDays, onSearch }) {
  const { user } = useAuth();
  const [draft, setDraft] = useState(value);
  const [recent, setRecent] = useState(() => loadRecent(user));
  const set = (patch) => setDraft((d) => ({ ...d, ...patch }));
  const bySido = markets.reduce((g, m) => ((g[m.sido] = g[m.sido] ?? []).push(m), g), {});
  const marketName = (c) => markets.find((m) => m.code === c)?.name ?? "";
  const label = (d) => {
    const i = itemOf(d.item);
    const v = i?.varieties.find((x) => x.id === d.variety);
    return [i?.name, v ? v.label : "전체 품종", marketName(d.market)].join(" / ");
  };

  const search = () => {
    if (user) {
      const next = [draft, ...recent.filter((r) => label(r) !== label(draft))].slice(0, 4);
      setRecent(next); saveRecent(user, next);
    }
    onSearch(draft);
  };
  const removeRecent = (r) => { const next = recent.filter((x) => x !== r); setRecent(next); saveRecent(user, next); };
  const reset = () => setDraft({ ...value, item: ITEMS50[0].code, variety: "", date: addDays(today, 30) });
  const horizon = daysBetween(today, draft.date);

  return (
    <section className="card ps">
      <div className="ps-row">
        <span className="ps-lb">예측 날짜</span>
        <div className="ps-fields">
          <input type="date" className="input ps-date" value={draft.date} min={addDays(today, 1)} max={addDays(today, maxDays)}
            onChange={(e) => e.target.value && set({ date: e.target.value })} aria-label="예측 날짜" />
          <div className="ps-chips">
            {horizons.map((h) => (
              <button key={h.days} type="button" className={`ps-chip ${horizon === h.days ? "on" : ""}`} onClick={() => set({ date: addDays(today, h.days) })}>{h.label} 후</button>
            ))}
          </div>
        </div>
      </div>
      <div className="ps-row">
        <span className="ps-lb">품목</span>
        <CropSelect item={draft.item} variety={draft.variety} onChange={set} warn />
      </div>
      <div className="ps-row">
        <span className="ps-lb">도매시장</span>
        <div className="ps-fields">
          <select className="input ps-sel wide" value={draft.market} onChange={(e) => set({ market: e.target.value })} aria-label="도매시장">
            {Object.entries(bySido).map(([sido, ms]) => (
              <optgroup key={sido} label={sido}>{ms.map((m) => <option key={m.code} value={m.code}>{m.name}</option>)}</optgroup>
            ))}
          </select>
        </div>
      </div>
      <div className="ps-foot">
        <div className="ps-recent">
          {user && recent.length > 0 && <span className="ps-rl">최근 검색</span>}
          {user && recent.map((r) => (
            <span key={label(r)} className="ps-tag">
              <button type="button" onClick={() => { setDraft(r); onSearch(r); }}>{label(r)} · {shortDate(r.date)}</button>
              <button type="button" className="x" aria-label="최근 검색 지우기" onClick={() => removeRecent(r)}>×</button>
            </span>
          ))}
        </div>
        <button type="button" className="ps-reset" onClick={reset}>↻ 선택초기화</button>
        <button type="button" className="ps-go" onClick={search}>검색하기</button>
      </div>
    </section>
  );
}
