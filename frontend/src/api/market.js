// 시세·날씨 (Spring 담당). 지금은 가짜 데이터를 돌려준다.
// Spring API 가 생기면 각 함수 안쪽만 request(SPRING_API_BASE, "/api/...") 로 바꾸면 화면은 그대로 동작한다.
// 기준: 따로 고르지 않는 가격은 모두 전국 도매시장(national) · 상 등급(HIGH) · 원/kg. 안내는 서비스 소개 화면에 있다.
import { DATA_SOURCE, fake } from "./client";
import { liveRegionalWeather } from "./live/kmaWeather";
import {
  MARKETS, mockGradePrices, mockMarketCompare, mockOriginPrices, mockPriceHistory, mockTodayPrices, mockVolumeTrend,
} from "../mocks/market";
import { mockRegionalWeather } from "../mocks/weather";

/** 도매 등급 (DB price_daily.grade 와 같은 코드). 화면 기본값은 HIGH(상) */
export const GRADES = [
  { code: "SPECIAL", name: "특" },
  { code: "HIGH", name: "상" },
  { code: "MID", name: "중" },
  { code: "LOW", name: "하" },
  { code: "ALL", name: "평균" },
];
export const DEFAULT_MARKET = "national";
export const DEFAULT_GRADE = "HIGH";

/** 오늘의 시세 = 전국 도매시장 · 상 등급 + 전국 소매가 (홈 카드·상단 띠·검색·마이페이지) */
export const getTodayPrices = () => fake(mockTodayPrices());

/** 도매시장 목록 (전국 평균 + 32곳) */
export const getMarkets = () => fake(MARKETS);

/** 등급별(특·상·중·하·평균) 가격 + 전국 소매가, 최근 5거래일 */
export const getGradePrices = (item, { market, date } = {}) => fake(mockGradePrices(item, { market, date }));

/** 한 등급의 날짜별 가격·최고·최저·반입량 + 전국 소매가 */
export const getPriceHistory = (item, { market, grade, date, days } = {}) => fake(mockPriceHistory(item, { market, grade, date, days }));

/** 출하지역(시·도)별 가격·반입량 */
export const getOriginPrices = (item, { market, date } = {}) => fake(mockOriginPrices(item, { market, date }));

/** 순(10일) 단위 출하지역별 반입량 + 이번 순 요약 */
export const getVolumeTrend = (item, { market, date } = {}) => fake(mockVolumeTrend(item, { market, date }));

/** 시장별 오늘 가격 (통합 검색) */
export const getMarketCompare = (item) => fake(mockMarketCompare(item));

/** 홈 날씨 지도: 시·도 17곳의 오늘 날씨와 특보 (테스트 모드에서는 기상청 실제 값) */
export const getRegionalWeather = () => (DATA_SOURCE === "live" ? liveRegionalWeather() : fake(mockRegionalWeather()));
