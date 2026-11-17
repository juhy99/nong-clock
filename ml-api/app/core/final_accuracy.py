"""[11-17] 최종 모델 시험 정확도로 '이 예측, 믿을 만한가요?' (error_pct · confidence) 를 정한다.

전에는 범위(하한·상한) 폭의 절반을 '오차'라 불러서, 품목과 상관없이 기간만으로 같은 값이 나오고
가까운 날일수록 오차가 크게 나왔다 (3일 뒤 49.6% > 1년 뒤 34.7%). 관리자 모델 성능·소개와도 숫자가 달랐다.

지금: shared/final_model_accuracy.json 의 units (예측 단위 320개 × 거리 묶음 d1·d2·m1·m2·m3, [최종, 작년 같은 시기])
  - 품종을 고르면 그 품종 단위들, 아니면 품목 단위들의 '최종' 정확도 중앙값 (같은 정의: 100 − 평균 |예측÷실제 − 1|)
  - 거리 묶음 (달력 일): 1~7일 = d1(1~5거래일) · 8~20일 = d2(6~14거래일) · 21~91일 = m1(1~3달) · 92~182일 = m2(4~6달) · 183일~ = m3(7~12달)
  - m1~m3 은 '달 평균' 정확도 (그날 하루 값은 이보다 덜 맞음) → 화면 문구에 '달 평균'을 밝힌다
  - 단위가 하나도 없으면 전체(day_total·month_total) 값
"""

from statistics import median

from app.core.shared import load

_BUCKETS = (("d1", 7), ("d2", 20), ("m1", 91), ("m2", 182), ("m3", 10_000))
_TOTAL = {"d1": ("day_total", "H1-5"), "d2": ("day_total", "H6-14"), "m1": ("month_total", "h1-3"),
          "m2": ("month_total", "h4-6"), "m3": ("month_total", "h7-12")}


def bucket(days: int) -> str:
    for b, top in _BUCKETS:
        if days <= top:
            return b
    return "m3"


def _units() -> dict[str, dict]:
    return {u["unit"]: u for u in load("final_model_accuracy.json")["units"]}


def _groups() -> dict[tuple[str, str], list[str]]:
    out = {}
    for it in load("items50.json")["items"]:
        allu = []
        for v in it.get("varieties", []):
            out[(it["code"], v["id"])] = v["units"]
            allu += v["units"]
        out[(it["code"], "")] = allu
    return out


def accuracy(item: str, variety: str, days: int) -> tuple[float, str]:
    """(정확도 %, 묶음 이름) — 품종 → 품목 → 전체 순서로 찾음"""
    b = bucket(days)
    U, G = _units(), _groups()
    for key in ((item, variety or ""), (item, "")):
        vals = [U[u][b][0] for u in G.get(key, []) if u in U and b in U[u] and U[u][b]]
        if vals:
            return round(median(vals), 1), b
    sect, k = _TOTAL[b]
    return float(load("final_model_accuracy.json")[sect][k]["final"]), b
