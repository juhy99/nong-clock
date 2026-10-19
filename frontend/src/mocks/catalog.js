// ML API(GET /items, /regions, /horizons)가 꺼져 있을 때 쓰는 예비 데이터.
// 실제 목록의 기준은 ml-api/app/core/catalog.py 이다. 화면 코드는 이 파일을 직접 쓰지 말고 api/ml.js 를 거친다.
export const ITEMS = [
  { code: "potato", name: "감자", unit: "kg", category: "근채류", emoji: "🥔" },
  { code: "onion", name: "양파", unit: "kg", category: "조미채소", emoji: "🧅" },
  { code: "carrot", name: "당근", unit: "kg", category: "근채류", emoji: "🥕" },
  { code: "apple", name: "사과", unit: "kg", category: "과일류", emoji: "🍎" },
  { code: "watermelon", name: "수박", unit: "kg", category: "과채류", emoji: "🍉" },
  { code: "napa_cabbage", name: "배추", unit: "kg", category: "엽채류", emoji: "🥬" },
  { code: "radish", name: "무", unit: "kg", category: "근채류", emoji: "🌱" },
  { code: "tomato", name: "토마토", unit: "kg", category: "과채류", emoji: "🍅" },
  { code: "cabbage", name: "양배추", unit: "kg", category: "엽채류", emoji: "🥗" },
  { code: "sweet_potato", name: "고구마", unit: "kg", category: "근채류", emoji: "🍠" },
  { code: "button_mushroom", name: "양송이", unit: "kg", category: "버섯류", emoji: "🍄" },
  { code: "pear", name: "배", unit: "kg", category: "과일류", emoji: "🍐" },
  { code: "king_oyster_mushroom", name: "새송이", unit: "kg", category: "버섯류", emoji: "🍄" },
  { code: "green_onion", name: "대파", unit: "kg", category: "조미채소", emoji: "🌿" },
  { code: "mandarin", name: "감귤", unit: "kg", category: "과일류", emoji: "🍊" },
  { code: "enoki_mushroom", name: "팽이버섯", unit: "kg", category: "버섯류", emoji: "🍄" },
];

export const REGIONS = [{ code: "national", name: "전국" }];

export const HORIZONS = [
  { days: 7, label: "1주" },
  { days: 14, label: "2주" },
  { days: 30, label: "1개월" },
];

// 가짜 시세용 기준가(원/kg). 팀원 모델 v1 결과의 7일 예측값 근처.
export const BASE_PRICE = {
  potato: 1420, onion: 1200, carrot: 2100, apple: 4990, watermelon: 2290,
  napa_cabbage: 800, radish: 770, tomato: 3810, cabbage: 1390, sweet_potato: 2050,
  button_mushroom: 17730, pear: 2540, king_oyster_mushroom: 3270, green_onion: 1470,
  mandarin: 5200, enoki_mushroom: 1870,
};
