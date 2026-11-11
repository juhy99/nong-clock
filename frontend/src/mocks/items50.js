// [샘플] 품목 50개 × 세부 품종 (shared/items50.json). 가격 예측 입력(부류 → 품목 → 품종)과 작물 추천의 품종 묶기에 쓴다.
// 품종별 가격 수준은 아직 모델 결과가 없어서 가짜 값: 품목 예측 × 품종 계수(0.8~1.25, 품종마다 고정)
import DATA from "../../../shared/items50.json";
import { seeded } from "../utils/format";

export const ITEMS50 = DATA.items;
export const IN50 = new Set(ITEMS50.map((i) => i.code));
export const CATEGORIES50 = [...new Set(ITEMS50.map((i) => i.category))];
export const itemOf = (code) => ITEMS50.find((i) => i.code === code);
/** 품종 (11-11 팀 기준): 화면묶음 이름 = 품목 이름이면 예측 단위마다, 그 밖의 화면묶음은 묶음째 하나. units = 들어가는 예측 단위 이름들 */
export const varietyOf = (code, id) => (id ? itemOf(code)?.varieties.find((v) => v.id === id) : undefined);
/** 고르는 목록: 파일 순서 그대로 (품목 이름 묶음의 단위 → 따로 품종 → 기타). 품종이 "기타" 하나뿐이면(= 품목 전체) 목록을 비움 */
export const sortedVarieties = (it) => {
  const vs = it?.varieties ?? [];
  return vs.length === 1 && vs[0].kind === "other" ? [] : vs;
};
/** 품종 가격 계수 (가짜) */
export const varietyFactor = (id) => (id ? 0.8 + seeded(`v|${id}`)() * 0.45 : 1);
