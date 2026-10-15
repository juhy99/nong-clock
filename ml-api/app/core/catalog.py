"""품목·지역 코드표.

프론트(URL 쿼리 `?item=cabbage`)와 Spring이 같은 코드를 쓰도록 여기서 한 번만 정의한다.
base_price 는 더미 예측기가 쓰는 기준 시세(원)이며, 실제 모델이 붙으면 DB 시세로 대체된다.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    code: str
    name: str
    unit: str
    category: str
    base_price: int


ITEMS: dict[str, Item] = {
    item.code: item
    for item in [
        Item("cabbage", "배추", "10kg", "엽채류", 12400),
        Item("lettuce", "상추", "4kg", "엽채류", 18200),
        Item("onion", "양파", "15kg", "조미채소", 16900),
        Item("garlic", "깐마늘", "1kg", "조미채소", 9800),
        Item("hot_pepper", "청양고추", "10kg", "과채류", 54000),
        Item("tomato", "토마토", "5kg", "과채류", 21500),
        Item("strawberry", "딸기", "2kg", "과일류", 32000),
        Item("potato", "감자", "20kg", "근채류", 38500),
    ]
}

REGIONS: dict[str, str] = {
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

HORIZONS = (7, 14, 30)
