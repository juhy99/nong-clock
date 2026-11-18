"""작물별 주산지 (11-18) — 작물 추천에서 '그 시·도에서 실제로 많이 기르는가'를 순위에 반영.

기준은 저장소 맨 위 shared/crop_regions.json (python-ml/crops/build_crop_regions.py 가 만듦).
값 = 공영 도매시장에 들어온 국산 물량 가운데 그 시·도산 몫(%), 최근 3년. 재배면적이 아니라 '도매시장 반입 산지' 기준.
- 몫이 main_pct(10%) 이상 → "main" 주산지: 소득과 상관없이 위로
- 몫이 rare_pct(1%) 미만 → "rare" 거의 안 기름: 아래로 + 안내 (조사 수량은 전국 평균이라 그 지역에서는 그만큼 거두기 어려울 수 있음)
- 그 사이 · 표에 없는 작물(쌀·콩) · 시·도를 모를 때(전국) → None: 순위 그대로
소득 숫자는 바꾸지 않는다 (시·도별 수량 조사 자료가 없음). 순서와 안내만 바꾼다.
"""

from app.core.shared import load

_DATA = load("crop_regions.json")
MAIN_PCT: float = _DATA["main_pct"]
RARE_PCT: float = _DATA["rare_pct"]
PERIOD: tuple[str, str] = tuple(_DATA["period"])
SHARE: dict[str, dict[str, float]] = _DATA["share"]


def share(crop: str, region: str | None) -> float | None:
    """그 작물 국산 반입량 가운데 그 시·도산 몫(%). 자료가 없으면 None"""
    s = SHARE.get(crop)
    return s.get(region) if s and region else None


def tier(crop: str, region: str | None) -> str | None:
    p = share(crop, region)
    if p is None:
        return None
    return "main" if p >= MAIN_PCT else "rare" if p < RARE_PCT else None


RANK = {"main": 0, None: 1, "rare": 2}


def pct_text(p: float) -> str:
    return "0.1% 미만" if p < 0.1 else f"{p:g}%"


def note(crop: str, name: str, region: str | None) -> str | None:
    """화면에 그대로 보여 줄 한 줄 (주산지 · 거의 안 기름). 그 밖에는 None"""
    t, p = tier(crop, region), share(crop, region)
    if t == "main":
        return f"{region} 주산지 작물이에요 — 도매시장에 들어온 국산 {name}의 {pct_text(p)}가 {region}산이에요"
    if t == "rare":
        return (f"{region}에서는 거의 기르지 않는 작물이에요 (도매시장에 들어온 국산 {name} 중 {region}산 {pct_text(p)}). "
                f"수량은 전국 평균 조사값이라 여기서는 그만큼 거두기 어려울 수 있어 아래로 내렸어요")
    return None


BASIS = f"주산지는 재배면적이 아니라 공영 도매시장에 들어온 국산 물량의 산지로 봤어요 ({PERIOD[0][:4]}.{int(PERIOD[0][5:7])}~{PERIOD[1][:4]}.{int(PERIOD[1][5:7])})"


def _josa(word: str, with_batchim: str, without: str) -> str:
    """받침이 있으면 with_batchim, 없으면 without (제주가 · 경북이)"""
    return with_batchim if (ord(word[-1]) - 0xAC00) % 28 else without


def notice(region: str | None, crops: list[str], shown: list[str | None]) -> str | None:
    """결과 위에 보여 줄 '순서를 이렇게 정했어요' 안내 (11-18). crops = 결과에 나온 작물, shown = 그 작물에 실제로 붙은 묶음.
    - 주산지·거의 안 기름이 하나라도 붙었으면: 순서 규칙 + 자료 기준 + 소득 1위가 아닐 수 있음
    - 비교한 작물이 모두 '거의 안 기름'이라 규칙을 안 쓴 때(세종, 제주 시설 등): 그 사실을 알림
    - 그 밖(전국, 자료 없는 작물만, 모두 보통): 안내 없음"""
    if not region or not crops:
        return None
    if any(shown):
        return (f"순서는 이렇게 정했어요: {region}{_josa(region, '이', '가')} 주산지인 작물을 먼저, 그다음은 소득이 높은 순, {region}에서 거의 기르지 않는 작물은 아래에 뒀어요. "
                f"그래서 1번 작물이 소득 1위가 아닐 수 있어요. {BASIS}. 소득 금액은 지역과 상관없이 전국 평균 조사값으로 계산한 그대로예요.")
    if all(tier(c, region) == "rare" for c in crops):
        return (f"지금 비교한 작물은 모두 도매시장에 {region}산이 거의 들어오지 않는 작물이에요 (작물마다 {RARE_PCT:g}% 미만). "
                f"지역으로는 순서를 가릴 수 없어 소득이 높은 순으로만 줄 세웠어요. 수량은 전국 평균 조사값이라 {region}에서는 그만큼 거두기 어려울 수 있어요. {BASIS}.")
    return None
