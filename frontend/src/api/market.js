// 시세·수급·날씨 (Spring 담당). 지금은 가짜 데이터를 돌려준다.
// Spring API 가 생기면 각 함수 안쪽만 request(SPRING_API_BASE, "/api/...") 로 바꾸면 화면은 그대로 동작한다.
import { fake } from "./client";
import { mockMarketCompare, mockPriceHistory, mockSupply, mockTodayPrices } from "../mocks/market";
import { mockRegionalWeather } from "../mocks/weather";

/** 오늘의 시세 (홈 카드·상단 띠·시세 표). 직전 조사일(compared_date) 대비 변동 포함 */
export const getTodayPrices = () => fake(mockTodayPrices());

/** 품목 최근 시세 추이 (도매/소매, 원/kg) */
export const getPriceHistory = (item, days = 30) => fake(mockPriceHistory(item, days));

/** 유통처(시장)별 가격 비교 */
export const getMarketCompare = (item) => fake(mockMarketCompare(item));

/** 월별 생산량 vs 평년 */
export const getSupply = (item) => fake(mockSupply(item));

/** 홈 날씨 지도: 시·도 17곳의 오늘 날씨와 특보 */
export const getRegionalWeather = () => fake(mockRegionalWeather());
