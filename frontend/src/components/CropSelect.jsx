import { CATEGORIES50, ITEMS50, itemOf, sortedVarieties } from "../mocks/items50";
import { LOW_ACCURACY } from "../mocks/accuracy";

/**
 * 부류 → 품목 → 품종 고르기 (50품목). onChange({ item, variety })
 * only: 고를 수 있는 품목 코드 Set (없으면 50개 전부)
 */
export default function CropSelect({ item, variety, onChange, only, warn = false }) {
  const list = only ? ITEMS50.filter((i) => only.has(i.code)) : ITEMS50;
  const cats = CATEGORIES50.filter((c) => list.some((i) => i.category === c));
  const it = itemOf(item);
  const category = it?.category ?? cats[0];
  const pickItem = (code) => onChange({ item: code, variety: "" });
  return (
    <div className="cs">
      <label className="cs-f"><span>부류</span>
        <select className="input" value={category} onChange={(e) => pickItem(list.find((i) => i.category === e.target.value).code)}>
          {cats.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
      <label className="cs-f"><span>품목</span>
        <select className="input" value={item} onChange={(e) => pickItem(e.target.value)}>
          {list.filter((i) => i.category === category).map((i) => (
            <option key={i.code} value={i.code}>{i.name}{warn && LOW_ACCURACY.has(i.code) ? " (!)" : ""}</option>
          ))}
        </select>
      </label>
      <label className="cs-f"><span>품종</span>
        <select className="input" value={variety} onChange={(e) => onChange({ item, variety: e.target.value })}>
          <option value="">전체</option>
          {sortedVarieties(it).map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
        </select>
      </label>
    </div>
  );
}
