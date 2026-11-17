// 가격 예측 모델 오차 (품목·예측 기간별 WAPE, 검증 기간). 기준은 shared/model_accuracy.json 한 파일
// (ml-api/app/core/accuracy.py 도 같은 파일·같은 규칙). 오차 범위(띠)·신뢰도·"참고용" 표시가 모두 여기서 나온다.
import ACC from "../../../shared/model_accuracy.json";
import FINAL from "../../../shared/final_model_accuracy.json";
import ITEMS50 from "../../../shared/items50.json";

export const ACCURACY = ACC;
export const ANCHORS = ACC.horizons.map((h) => h.days); // 7 · 14 · 30 · 90 · 180
export const MODEL_MAX_DAYS = 180; // 모델이 있는 가장 먼 예측(6개월). 그보다 먼 날은 참고용
const FAR_WIDEN = 0.5; // 6개월 → 1년 사이 오차를 6개월 값보다 최대 50% 넓게

const wapeTable = (item) => ACC.items[item]?.wape ?? {};
const at = (item, d) => wapeTable(item)[d] ?? ACC.average_wape[d];

/** 예측 t일 뒤 오차(±%, WAPE). 기간 사이는 이어서, 1주보다 가까우면 √ 비율로 줄이고, 6개월보다 멀면 넓힘 */
export function errorPct(item, t) {
  if (t <= ANCHORS[0]) return at(item, ANCHORS[0]) * Math.sqrt(Math.max(t, 1) / ANCHORS[0]);
  for (let i = 1; i < ANCHORS.length; i++) {
    const a = ANCHORS[i - 1], b = ANCHORS[i];
    if (t <= b) return at(item, a) + ((at(item, b) - at(item, a)) * (t - a)) / (b - a);
  }
  return at(item, MODEL_MAX_DAYS) * (1 + (FAR_WIDEN * Math.min(t - MODEL_MAX_DAYS, 185)) / 185);
}

/** t일 뒤가 속한 예측 기간 (1주·2주·1개월·3개월·6개월) */
export const bucketOf = (t) => (t <= 10 ? 7 : t <= 21 ? 14 : t <= 60 ? 30 : t <= 135 ? 90 : 180);
export const bucketLabel = (d) => ACC.horizons.find((h) => h.days === d)?.label ?? `${d}일`;

/** 참고용 표시: "far" = 6개월보다 먼 날, "baseline" = 이 품목·기간은 기준선(오늘 가격 그대로)보다 나쁨, null = 아님 */
export function referenceOf(item, t) {
  if (t > MODEL_MAX_DAYS) return "far";
  return (ACC.items[item]?.reference_only ?? []).includes(bucketOf(t)) ? "baseline" : null;
}

/** 신뢰도 지수 = 100 − 오차(%) (참고용이면 화면에 따로 표시) */
export const confidenceOf = (item, t) => Math.max(0, Math.round(100 - errorPct(item, t)));

/** 화면 안내용 (11-17): 최종 모델 시험 정확도 "1~5거래일 77.8% · … · 7~12달 83.5%(달 평균)" — 관리자 모델 성능과 같은 숫자 */
export const averageText = () => [
  ["1~5거래일", FINAL.day_total["H1-5"].final], ["6~14거래일", FINAL.day_total["H6-14"].final],
  ["1~3달", FINAL.month_total["h1-3"].final], ["4~6달", FINAL.month_total["h4-6"].final], ["7~12달", FINAL.month_total["h7-12"].final],
].map(([l, v]) => `${l} ${v}%`).join(" · ");

// 예측 정확도가 낮은 품목 (11-17, 최종 모델): 품목 단위 중앙값이 1~5거래일 70% 미만 또는 1~3달 75% 미만 → 이름 옆 (!)
//   (전에는 옛 107품목 모델 오차로 정해 지금 모델과 맞지 않았음)
const med = (a) => { const s = [...a].sort((x, y) => x - y); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
const UNIT_ACC = Object.fromEntries(FINAL.units.map((u) => [u.unit, u]));
export const LOW_ACCURACY = new Set(ITEMS50.items.filter((it) => {
  const us = it.varieties.flatMap((v) => v.units).map((u) => UNIT_ACC[u]).filter(Boolean);
  const d1 = med(us.filter((u) => u.d1).map((u) => u.d1[0])), m1 = med(us.filter((u) => u.m1).map((u) => u.m1[0]));
  return (d1 != null && d1 < 70) || (m1 != null && m1 < 75);
}).map((it) => it.code));
// 11-17: 품종도 같은 기준 (예: 포도 샤인마스캇 1~5거래일 47.3 · 1~3달 26.8 → (!))
export const LOW_ACCURACY_VARIETY = new Set(ITEMS50.items.flatMap((it) => it.varieties).filter((v) => {
  const us = v.units.map((u) => UNIT_ACC[u]).filter(Boolean);
  const d1 = med(us.filter((u) => u.d1).map((u) => u.d1[0])), m1 = med(us.filter((u) => u.m1).map((u) => u.m1[0]));
  return (d1 != null && d1 < 70) || (m1 != null && m1 < 75);
}).map((v) => v.id));
