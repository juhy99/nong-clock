// 가격 예측 모델 오차 (품목·예측 기간별 WAPE, 검증 기간). 기준은 shared/model_accuracy.json 한 파일
// (ml-api/app/core/accuracy.py 도 같은 파일·같은 규칙). 오차 범위(띠)·신뢰도·"참고용" 표시가 모두 여기서 나온다.
import ACC from "../../../shared/model_accuracy.json";

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

/** 화면 안내용: 예측 기간별 107품목 평균 오차 "1주 약 18% · 2주 약 20% · …" */
export const averageText = () => ACC.horizons.map((h) => `${h.label} 약 ${Math.round(ACC.average_wape[h.days])}%`).join(" · ");

// [샘플] 예측 정확도가 낮은 품목: 1개월 오차 35% 이상 또는 참고용 기간이 있는 품목 (기준은 추후 확정)
export const LOW_ACC_LIMIT = 35;
export const LOW_ACCURACY = new Set(Object.entries(ACC.items).filter(([, r]) => (r.wape["30"] ?? 0) >= LOW_ACC_LIMIT || r.reference_only.length).map(([c]) => c));
