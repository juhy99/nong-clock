// [샘플] 품목 50개 × 세부 품종 (shared/items50.json). 가격 예측 입력(부류 → 품목 → 품종)과 작물 추천의 품종 묶기에 쓴다.
// 품종별 가격 수준은 아직 모델 결과가 없어서 가짜 값: 품목 예측 × 품종 계수(0.8~1.25, 품종마다 고정)
import DATA from "../../../shared/items50.json";
import { seeded } from "../utils/format";

export const ITEMS50 = DATA.items;
export const IN50 = new Set(ITEMS50.map((i) => i.code));
export const CATEGORIES50 = [...new Set(ITEMS50.map((i) => i.category))];
export const itemOf = (code) => ITEMS50.find((i) => i.code === code);
export const varietyOf = (code, id) => itemOf(code)?.varieties.find((v) => v.id === id);
/** 화면에 고를 수 있게 이름 있는 품종을 먼저, "기타(철·산지)" 는 뒤로 */
export const sortedVarieties = (it) => [...(it?.varieties ?? [])].sort((a, b) => (a.kind === "other") - (b.kind === "other") || b.share - a.share);
/** 품종 가격 계수 (가짜) */
export const varietyFactor = (id) => (id ? 0.8 + seeded(`v|${id}`)() * 0.45 : 1);
/** 작물 추천에서 품종으로 나눌 때 쓰는 품종 (이름 있는 품종, 물량 비중 3% 이상, 최대 4개) */
export const namedVarieties = (code) => (itemOf(code)?.varieties ?? []).filter((v) => v.kind !== "other" && v.share >= 3).slice(0, 4);
