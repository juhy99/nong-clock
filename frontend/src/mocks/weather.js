// 지역별 농업 날씨 가짜 데이터. 실제로는 Spring 이 기상청 단기예보·기상특보를 시·도별로 모아 돌려준다.
import { seeded, todayIso } from "../utils/format";

/** 지도(@svg-maps/south-korea)의 지역 id → 이름. 회원 지역(SIDO)과 같은 이름을 쓴다. */
export const WEATHER_REGIONS = {
  seoul: "서울", busan: "부산", daegu: "대구", incheon: "인천", gwangju: "광주", daejeon: "대전",
  ulsan: "울산", sejong: "세종", gyeonggi: "경기", gangwon: "강원", "north-chungcheong": "충북",
  "south-chungcheong": "충남", "north-jeolla": "전북", "south-jeolla": "전남",
  "north-gyeongsang": "경북", "south-gyeongsang": "경남", jeju: "제주",
};

// 위도가 높을수록, 산간일수록 서늘하게 (대략적인 차이)
const OFFSET = {
  seoul: 0, incheon: 0, gyeonggi: -1, gangwon: -4, "north-chungcheong": -1, sejong: 0, daejeon: 1,
  "south-chungcheong": 0, "north-jeolla": 1, gwangju: 2, "south-jeolla": 2, "north-gyeongsang": 0,
  daegu: 2, ulsan: 3, busan: 4, "south-gyeongsang": 3, jeju: 6,
};
const SKY = [["☀️", "맑음"], ["🌤️", "구름 조금"], ["⛅", "구름 많음"], ["☁️", "흐림"], ["🌧️", "비"]];
const WARNINGS = { gangwon: "서리 주의보", "north-gyeongsang": "서리 주의보", jeju: "강풍 주의보" };
const NOTES = [
  "일조량 평년 대비 -18% · 시설재배 보광 권장",
  "일교차 큼 · 엽채류 냉해 주의",
  "건조한 날씨 · 노지 관수 필요",
  "강수 예보 · 수확 일정 조정 권장",
  "작물 생육에 무난한 날씨",
];

export function mockRegionalWeather() {
  const rand = seeded(`weather|${todayIso()}`);
  const base = 13 + Math.round(rand() * 4);
  const regions = Object.entries(WEATHER_REGIONS).map(([id, name]) => {
    const r = seeded(`weather|${todayIso()}|${id}`);
    const temp = base + OFFSET[id] + Math.round((r() - 0.5) * 3);
    const [icon, sky] = SKY[Math.floor(r() * SKY.length)];
    return {
      id,
      name,
      temp,
      min: temp - 5 - Math.round(r() * 3),
      max: temp + 3 + Math.round(r() * 3),
      icon,
      sky,
      rain_prob: sky === "비" ? 60 + Math.round(r() * 30) : Math.round(r() * 40),
      humidity: 45 + Math.round(r() * 45),
      wind: Math.round((1 + r() * 6) * 10) / 10,
      soil_temp: temp + Math.round((r() - 0.3) * 4),
      warning: WARNINGS[id] ?? null,
      note: NOTES[Math.floor(r() * NOTES.length)],
    };
  });
  return { base_time: `${todayIso()}T05:00:00+09:00`, regions };
}
