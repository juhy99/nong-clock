"""작물별 알맞은 흙 pH (작물 추천: 기존 작물 → 흙 pH 어림 → 후보 작물 순위 내림).

기준은 저장소 맨 위 shared/soil_ph.json (화면 frontend/src/mocks/soil_ph.js 도 같은 파일을 읽음).
출처: 팀 자료 「작물별 땅 조건」 v4 엑셀 '작물별_조건' 시트. 값이 없는 작물은 추정해서 채우지 않는다.
- 흙 pH 어림 = 기존 작물 알맞은 범위의 가운데 (그 작물에 맞춰 관리해 왔다고 봄)
- 흙 pH 가 후보 작물 최고값보다 DEMOTE_GAP(0.5) 이상 높으면 → pH 를 내리는 데 몇 달 걸림 → 추천 맨 아래로
- 0.5 보다 덜 높으면 "near", 최저값보다 낮으면 "raise"(석회로 몇 주) → 순위 그대로, 안내만
"""

from dataclasses import dataclass

from app.core.shared import load


@dataclass(frozen=True)
class SoilPh:
    name: str
    min: float | None
    max: float | None
    memo: str


_DATA = load("soil_ph.json")
DEMOTE_GAP: float = _DATA["demote_gap"]
CROP_MAP: dict[str, str] = _DATA["crop_map"]
SOIL_PH: dict[str, SoilPh] = {c["name"]: SoilPh(c["name"], c["min"], c["max"], c["memo"]) for c in _DATA["crops"]}


def _r1(x: float) -> float:  # 소수 첫째 자리, JS Math.round 와 같게
    import math

    return math.floor(x * 10 + 0.5) / 10


def soil_ph_from_prev(prev: str | None) -> float | None:
    p = SOIL_PH.get(prev or "")
    return _r1((p.min + p.max) / 2) if p and p.min is not None else None


def ph_of(crop_code: str) -> SoilPh | None:
    """작물 표(shared/crops.json)의 soil_ph_name 을 먼저, 없으면 soil_ph.json 의 crop_map (11-13)"""
    from app.core.crop_catalog import CROPS  # 순환 import 피하려고 여기서

    c = CROPS.get(crop_code)
    return SOIL_PH.get((c.soil_ph_name if c else None) or CROP_MAP.get(crop_code, ""))


def ph_check(crop_code: str, soil: float | None) -> tuple[str, SoilPh | None, float] | None:
    """(kind, 작물 pH, 차이) — kind: lower(맨 아래로) · near · raise · ok · unknown. 흙 pH 를 모르면 None"""
    if soil is None:
        return None
    p = ph_of(crop_code)
    if not p or p.min is None:
        return ("unknown", p, 0.0)
    over = _r1(soil - p.max)
    if over >= DEMOTE_GAP:
        return ("lower", p, over)
    if over > 0:
        return ("near", p, over)
    if soil < p.min:
        return ("raise", p, _r1(p.min - soil))
    return ("ok", p, 0.0)
