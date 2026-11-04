// 작물별 알맞은 흙 pH. 기준은 shared/soil_ph.json 한 파일 (ml-api/app/core/soil_ph.py 도 같은 파일을 읽음)
// 출처: 팀 자료 「작물별_조건」 시트 (농사로 재배력·작목별 기술서, 2026-11-03 정리). 값이 없는 작물(null)은 추정해서 채우지 않음
import PH from "../../../shared/soil_ph.json";

export const SOIL_PH = PH.crops;
export const PH_OF_CROP = PH.crop_map; // 작물 추천 작물 코드 → 조건표 이름
export const PH_DEMOTE_GAP = PH.demote_gap; // 흙 pH 가 작물 최고값보다 이만큼 이상 높을 때만 내림 (11/4 결정: 0.5)
const BY_NAME = Object.fromEntries(SOIL_PH.map((p) => [p.name, p]));
export const phOf = (cropCode) => BY_NAME[PH_OF_CROP[cropCode]] ?? null;
export const phByName = (name) => BY_NAME[name] ?? null;

/** 기존 작물로 지금 흙 pH 어림: 그 작물 알맞은 범위의 가운데 (그 작물에 맞춰 관리해 왔다고 봄) */
export const soilPhFromPrev = (name) => {
  const p = BY_NAME[name];
  return p?.min != null ? Math.round(((p.min + p.max) / 2) * 10) / 10 : null;
};

/**
 * 후보 작물과 지금 흙 pH 비교 → { kind, min, max, gap } (ml-api app/core/soil_ph.py ph_check 와 같음)
 * - lower: 흙 pH 가 작물 최고값보다 0.5 이상 높음 → 낮춰야 함(달 단위로 걸림) → 추천 맨 아래로
 * - near: 0.5 보다 덜 높음 → 순위 그대로, 안내만
 * - raise: 흙 pH 가 작물 최저값보다 낮음 → 석회로 올리면 됨(몇 주) → 순위 그대로, 안내만
 */
const r1 = (x) => Math.round(x * 10) / 10;
export function phCheck(cropCode, soil) {
  if (soil == null) return null;
  const p = phOf(cropCode);
  if (!p || p.min == null) return { kind: "unknown", min: null, max: null, gap: 0 };
  const over = r1(soil - p.max);
  if (over >= PH_DEMOTE_GAP) return { kind: "lower", min: p.min, max: p.max, gap: over };
  if (over > 0) return { kind: "near", min: p.min, max: p.max, gap: over };
  if (soil < p.min) return { kind: "raise", min: p.min, max: p.max, gap: r1(p.min - soil) };
  return { kind: "ok", min: p.min, max: p.max, gap: 0 };
}
