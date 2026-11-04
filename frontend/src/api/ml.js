// ML API(FastAPI) 호출. 명세: docs/06_api_spec.md 1번 섹션.
// 서버가 꺼져 있으면 예비 데이터(mocks)로 대신 보여주고, 화면 상단에 "데모 데이터" 안내를 띄운다.
import { ML_API_BASE, request } from "./client";
import { HORIZONS, ITEMS, REGIONS } from "../mocks/catalog";
import { MARKETS } from "../mocks/market";
import { mockPredict, mockTopMovers } from "../mocks/prediction";
import { mockCropInfo, mockCropList, mockPlantingDates, mockPricePath, mockRecommendCrops } from "../mocks/recommend";

const listeners = new Set();
let offline = false;

/** ML API 연결이 끊겼는지 구독 (Layout 의 안내 배너용) */
export function onMlOffline(fn) {
  listeners.add(fn);
  fn(offline);
  return () => listeners.delete(fn);
}

function setOffline(v) {
  if (offline === v) return;
  offline = v;
  listeners.forEach((fn) => fn(v));
}

async function withFallback(call, fallback) {
  try {
    const data = await call();
    setOffline(false);
    return data;
  } catch (e) {
    if (e.status) throw e; // 서버가 응답한 오류(404, 422 등)는 그대로 알린다
    setOffline(true);
    return fallback();
  }
}

export const getItems = () => withFallback(() => request(ML_API_BASE, "/items"), () => ITEMS);
export const getRegions = () => withFallback(() => request(ML_API_BASE, "/regions"), () => REGIONS);
export const getHorizons = () => withFallback(() => request(ML_API_BASE, "/horizons"), () => HORIZONS);
/** 공영 도매시장 32곳 [{ code, name, sido, ... }] — 목록 기준은 ml-api/app/core/markets.py */
export const getMarkets = () => withFallback(() => request(ML_API_BASE, "/markets"), () => MARKETS.filter((m) => m.code !== "national"));

/** @param {{item: string, horizon: number, market?: string}} req  horizon 1~365, market = 도매시장 코드 */
export const predict = (req) =>
  withFallback(() => request(ML_API_BASE, "/predict", { method: "POST", body: req }), () => mockPredict(req));

export const getTopMovers = ({ horizon = 7, limit = 4 } = {}) =>
  withFallback(
    () => request(ML_API_BASE, `/predict/top-movers?horizon=${horizon}&limit=${limit}`),
    () => mockTopMovers(horizon, limit),
  );

// ── 작물 추천 (docs/06_api_spec.md 1-6) ──
export const getRecommendCrops = () => withFallback(() => request(ML_API_BASE, "/recommend/crops"), mockCropList);

/** 내 땅으로 작물 고르기. @param {{lands: {type: string, area_pyeong: number}[], start_date: string}} req */
export const recommendCrops = (req) =>
  withFallback(() => request(ML_API_BASE, "/recommend/crops", { method: "POST", body: req }), () => mockRecommendCrops(req));

/** 작물로 가장 좋은 심는 날 고르기. @param {{crop: string, area_pyeong: number}} req */
export const recommendPlantingDates = (req) =>
  withFallback(() => request(ML_API_BASE, "/recommend/planting-dates", { method: "POST", body: req }), () => mockPlantingDates(req));

/** 작물의 앞으로 13개월 예상 도매가 (주 단위) */
/** 작물 정보 탭: 작형·수량·경영비 */
export const getCropInfo = (code) => withFallback(() => request(ML_API_BASE, `/recommend/crops/${code}`), () => mockCropInfo(code));

export const getCropPricePath = (code) =>
  withFallback(() => request(ML_API_BASE, `/recommend/crops/${code}/prices`), () => mockPricePath(code));

/** 개발자 페이지: 응답 속도까지 재는 상태 확인 */
export async function pingMl() {
  const t0 = performance.now();
  try {
    const data = await request(ML_API_BASE, "/health", { timeoutMs: 3000 });
    return { ok: true, ms: Math.round(performance.now() - t0), detail: data };
  } catch (e) {
    return { ok: false, ms: null, detail: e.message };
  }
}
