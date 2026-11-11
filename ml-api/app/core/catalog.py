"""품목·지역·예측 기간 코드표.

예측 품목은 50개 — shared/items50.json (11-11, 화면 품목 고르기와 같은 목록, 순서 = 물량 순위). /items·/predict·/predict/top-movers 가 이 50개만 다룬다.
품목 정보(code4·기준가 등) 107개의 기준은 저장소 맨 위 shared/items.json 한 파일 (화면 frontend/src/mocks/catalog.js 도 같은 파일을 읽음).
품목을 추가·삭제할 때는 그 파일만 고치면 /items, /predict, /predict/top-movers 에 모두 반영된다.
- code: 영어 코드 (프론트 URL ?item=napa_cabbage, Spring 이 같이 씀). 기존 16개는 바꾸지 않는다
- code4: 공영도매 품목코드(4자리) — 모델 결과를 이 코드로 붙인다
- category: 공영 부류 (품목코드 앞 2자리), emoji 가 없으면 부류 기본 이모지
- base_price: 더미 예측기·가짜 시세용 기준가(원/kg) — 가짜 값. 실제 모델이 붙으면 DB 시세로 대체된다
가격 단위는 모든 품목 원/kg.
"""

from dataclasses import dataclass

from app.core.config import ENABLE_REGIONAL_FORECAST
from app.core.shared import load

PRICE_UNIT = "kg"


@dataclass(frozen=True)
class Item:
    code: str
    name: str
    category: str
    emoji: str
    base_price: int
    code4: str = ""
    unit: str = PRICE_UNIT


_CATALOG = load("items.json")
CATEGORY_EMOJI: dict[str, str] = _CATALOG["category_emoji"]
LEGACY_CODES: list[str] = _CATALOG["legacy_codes"]

# 순서 = 거래 물량이 많은 순
ITEMS: dict[str, Item] = {
    i["code"]: Item(i["code"], i["name"], i["category"], i["emoji"] or CATEGORY_EMOJI[i["category"]], i["base_price"], i["code4"])
    for i in _CATALOG["items"]
}
ITEMS_BY_CODE4: dict[str, Item] = {i.code4: i for i in ITEMS.values()}

# 예측 품목 50개 (11-11): items50.json 의 code 순서. 107개 안에 모두 있다
PREDICT_ITEMS: dict[str, Item] = {i["code"]: ITEMS[i["code"]] for i in load("items50.json")["items"]}

# 지역(예전 방식, /regions): 전국(national)만. 가격은 이제 도매시장별 — GET /markets, POST /predict 의 market (06_api_spec.md 1-2)
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

# 예측 기간: 화면의 빠른 선택 버튼 (일수 → 이름). 예측 자체는 1일 ~ MAX_HORIZON 일 중 아무 날이나 가능하다.
HORIZONS: dict[int, str] = {
    7: "1주",
    14: "2주",
    30: "1개월",
    90: "3개월",
    180: "6개월",
    365: "1년",
}
MAX_HORIZON = 365
BASE_DATE_BACK_DAYS = 365  # 기준일은 오늘부터 1년 전까지 고를 수 있다 (11-11)
MAX_HISTORY_DAYS = 400  # 기준일 앞 실제 시세는 최대 400일
LONG_RANGE_DAYS = 180  # 모델은 6개월까지만 검증 → 이보다 먼 예측은 오차 범위를 더 넓히고 화면에 "참고용" (accuracy.py)
