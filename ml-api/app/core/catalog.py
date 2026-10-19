"""품목·지역 코드표.

프론트(URL 쿼리 `?item=napa_cabbage`)와 Spring이 같은 코드를 쓰도록 여기서 한 번만 정의한다.
가격 단위는 모든 품목 **원/kg** 으로 통일한다.
base_price 는 더미 예측기가 쓰는 기준 시세(원/kg)이며, 실제 모델이 붙으면 DB 시세로 대체된다.
품목을 추가·삭제할 때는 이 목록만 고치면 /items, /predict, /predict/top-movers 에 모두 반영된다.
"""

from dataclasses import dataclass

from app.core.config import ENABLE_REGIONAL_FORECAST

PRICE_UNIT = "kg"


@dataclass(frozen=True)
class Item:
    code: str
    name: str
    category: str
    emoji: str
    base_price: int
    unit: str = PRICE_UNIT


ITEMS: dict[str, Item] = {
    item.code: item
    for item in [
        Item("potato", "감자", "근채류", "🥔", 1420),
        Item("onion", "양파", "조미채소", "🧅", 1200),
        Item("carrot", "당근", "근채류", "🥕", 2100),
        Item("apple", "사과", "과일류", "🍎", 4990),
        Item("watermelon", "수박", "과채류", "🍉", 2290),
        Item("napa_cabbage", "배추", "엽채류", "🥬", 800),
        Item("radish", "무", "근채류", "🌱", 770),
        Item("tomato", "토마토", "과채류", "🍅", 3810),
        Item("cabbage", "양배추", "엽채류", "🥗", 1390),
        Item("sweet_potato", "고구마", "근채류", "🍠", 2050),
        Item("button_mushroom", "양송이", "버섯류", "🍄", 17730),
        Item("pear", "배", "과일류", "🍐", 2540),
        Item("king_oyster_mushroom", "새송이", "버섯류", "🍄", 3270),
        Item("green_onion", "대파", "조미채소", "🌿", 1470),
        Item("mandarin", "감귤", "과일류", "🍊", 5200),
        Item("enoki_mushroom", "팽이버섯", "버섯류", "🍄", 1870),
    ]
}

# 지역: 지금은 전국(national) 예측만 제공한다.
# 지역별 모델이 준비되면 환경변수 ENABLE_REGIONAL_FORECAST=true 로 아래 PROVINCES 를 켠다.
# 켜거나 꺼도 API 형식은 그대로라 프론트·Spring 은 수정할 필요 없음.
NATIONAL = "national"

PROVINCES: dict[str, str] = {
    "gyeonggi": "경기",
    "gangwon": "강원",
    "chungbuk": "충북",
    "chungnam": "충남",
    "jeonbuk": "전북",
    "jeonnam": "전남",
    "gyeongbuk": "경북",
    "gyeongnam": "경남",
    "jeju": "제주",
}

REGIONS: dict[str, str] = {NATIONAL: "전국", **(PROVINCES if ENABLE_REGIONAL_FORECAST else {})}

# 예측 기간: 일수 → 화면 표시 이름. 기간을 바꾸려면 여기만 고치면 된다.
# 화면의 빠른 선택 버튼. 예측 자체는 1일 ~ MAX_HORIZON 일 중 아무 날이나 가능하다.
HORIZONS: dict[int, str] = {
    7: "1주",
    14: "2주",
    30: "1개월",
}
MAX_HORIZON = max(HORIZONS)
