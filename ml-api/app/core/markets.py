"""공영 도매시장 32곳 (가격 예측·작물 추천이 같이 씀).

- 시장 목록의 기준은 저장소 맨 위 shared/markets.json 한 파일 (화면 frontend/src/mocks/market.js 도 같은 파일을 읽음).
  시장을 지역 단위로 묶는 방식이 정해지면 그 파일과 이 모듈만 고친다.
- 시장 계수: 시장별 가격 = 전국 도매시장 평균 예측 × 계수(0.9~1.1). 프론트 시세 가짜 데이터와 같은 규칙이라
  두 화면의 숫자가 맞는다. 실제 시장별 모델이 붙으면 market_factor 자리(또는 예측기)만 바꾸면 된다.
- 작물 추천: 토지 위치(시·도) 안의 시장끼리 비교. 시·도 안에 시장이 없으면(세종·제주) 다른 지역 시장을 섞지 않고 전국 평균.
"""

from dataclasses import dataclass

from app.core.shared import load


@dataclass(frozen=True)
class Market:
    code: str
    name: str
    sido: str
    sigungu: str
    lat: float
    lon: float


_DATA = load("markets.json")
SIDO: list[str] = _DATA["sido"]
MARKETS: dict[str, Market] = {m["code"]: Market(m["code"], m["name"], m["sido"], m["sigungu"], m["lat"], m["lon"]) for m in _DATA["markets"]}
NATIONAL = "national"
NATIONAL_NAME = "전국 평균"
GARAK = "110001"


def markets_in_sido(sido: str) -> list[Market]:
    """그 시·도 안의 공영 도매시장 (없으면 빈 목록)"""
    return [m for m in MARKETS.values() if m.sido == sido]


def market_name(code: str) -> str:
    return NATIONAL_NAME if code == NATIONAL else MARKETS[code].name


def _seeded(text: str) -> float:
    """frontend/src/utils/format.js seeded() 의 첫 값과 같은 고정 난수 (0~1)"""
    M = 0xFFFFFFFF
    h = 2166136261
    for ch in text:
        h = ((h ^ ord(ch)) * 16777619) & M
    h = ((h ^ (h >> 15)) * 2246822507) & M
    h = ((h ^ (h >> 13)) * 3266489909) & M
    h ^= h >> 16
    return (h & M) / 4294967296


def market_factor(crop: str, market: str | None) -> float:
    if not market or market == "national":
        return 1.0
    return 0.9 + _seeded(f"m|{crop}|{market}") * 0.2
