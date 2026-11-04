"""가격 예측 모델 오차 (품목·예측 기간별 WAPE, 검증 기간 2025-07~).

기준은 저장소 맨 위 shared/model_accuracy.json (화면 frontend/src/mocks/accuracy.js 도 같은 파일·같은 규칙).
출처: 팀 결과 페이지 '107품목 가격 예측 결과'·'107품목 예측 방법'. 정답 = 공영도매시장 전국 경매 단가(원/kg).
- error_pct(item, t): t일 뒤 오차(±%). 1주·2주·1개월·3개월·6개월 사이는 이어서, 1주보다 가까우면 √ 비율로 줄이고,
  6개월보다 먼 날(최대 1년)은 모델이 없어 6개월 값보다 최대 50% 넓게
- reference_of(item, t): "far"(6개월보다 멂) · "baseline"(이 품목·기간은 기준선보다 나쁨) · None → 화면에 "참고용"
- confidence(item, t) = 100 − 오차
"""

import math

from app.core.shared import load

ACC = load("model_accuracy.json")
ANCHORS: list[int] = [h["days"] for h in ACC["horizons"]]
LABELS: dict[int, str] = {h["days"]: h["label"] for h in ACC["horizons"]}
MODEL_MAX_DAYS = 180
FAR_WIDEN = 0.5
AVERAGE: dict[int, float] = {int(k): v for k, v in ACC["average_wape"].items()}


def _at(item: str, d: int) -> float:
    return ACC["items"].get(item, {}).get("wape", {}).get(str(d), AVERAGE[d])


def error_pct(item: str, t: int) -> float:
    if t <= ANCHORS[0]:
        return _at(item, ANCHORS[0]) * math.sqrt(max(t, 1) / ANCHORS[0])
    for a, b in zip(ANCHORS, ANCHORS[1:]):
        if t <= b:
            return _at(item, a) + (_at(item, b) - _at(item, a)) * (t - a) / (b - a)
    return _at(item, MODEL_MAX_DAYS) * (1 + FAR_WIDEN * min(t - MODEL_MAX_DAYS, 185) / 185)


def bucket_of(t: int) -> int:
    return 7 if t <= 10 else 14 if t <= 21 else 30 if t <= 60 else 90 if t <= 135 else 180


def reference_of(item: str, t: int) -> str | None:
    if t > MODEL_MAX_DAYS:
        return "far"
    return "baseline" if bucket_of(t) in ACC["items"].get(item, {}).get("reference_only", []) else None


def confidence(item: str, t: int) -> int:
    return max(0, math.floor(100 - error_pct(item, t) + 0.5))  # JS Math.round 와 같게
