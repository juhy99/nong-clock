// ML API(GET /items, /markets, /horizons)가 꺼져 있을 때 쓰는 예비 데이터. 화면 코드는 이 파일을 직접 쓰지 말고 api/ml.js 를 거친다.
// 품목 107개의 기준은 shared/items.json 한 파일 (ml-api/app/core/catalog.py 도 같은 파일을 읽음). 품목을 바꿀 때는 그 파일만 고친다.
// code4 = 공영 품목코드(모델 결과를 붙이는 키), category = 공영 부류. 기존 16개 영어 코드는 URL·다른 화면에서 쓰므로 바꾸지 않는다.
import CATALOG from "../../../shared/items.json";

// 부류별 기본 이모지 (품목 이모지가 없을 때)
export const CATEGORY_EMOJI = CATALOG.category_emoji;
export const CATEGORIES = Object.keys(CATEGORY_EMOJI);

// 순서 = 거래 물량이 많은 순
export const ITEMS = CATALOG.items.map(({ code, name, code4, category, emoji }) => ({ code, name, code4, unit: "kg", category, emoji: emoji || CATEGORY_EMOJI[category] }));
// 예전부터 있던 16개 (뉴스 검색어 등 품목 수가 늘면 곤란한 곳에서 씀)
export const LEGACY_CODES = CATALOG.legacy_codes;

export const REGIONS = [{ code: "national", name: "전국" }];

export const HORIZONS = [
  { days: 7, label: "1주" },
  { days: 14, label: "2주" },
  { days: 30, label: "1개월" },
  { days: 90, label: "3개월" },
  { days: 180, label: "6개월" },
  { days: 365, label: "1년" },
];

// 가짜 시세·가짜 예측용 기준가(원/kg) — 가짜 값 (shared/items.json 의 base_price)
export const BASE_PRICE = Object.fromEntries(CATALOG.items.map((i) => [i.code, i.base_price]));
