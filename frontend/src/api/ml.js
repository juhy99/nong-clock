// ML API(FastAPI) 호출. 명세: docs/06_api_spec.md 1번 섹션.
// 서버가 꺼져 있으면 품목·지역·시장 목록만 저장소의 목록으로 대신하고(값이 아니라 이름표), 예측·추천 값은 오류로 알린다. 화면 위에 안내 띠.
import { ML_API_BASE, request } from "./client";
import { HORIZONS, ITEMS, REGIONS } from "../mocks/catalog";
import { MARKETS } from "../mocks/market";

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
    // 11-17: 예측·추천은 서버에서도 회원만 — 로그인 시간이 끝난 채 쓰고 있었으면 로그인 화면으로 (로그인 뒤 보던 화면으로 돌아옴)
    if (e.status === 401 && typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    }
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

/** @param {{item: string, horizon: number, market?: string, base_date?: string, history_days?: number, last_year?: boolean}} req
 *  horizon 1~365, market = 도매시장 코드, base_date = 기준일(오늘~1년 전), history_days = 앞쪽 실제 시세 일수, last_year = 작년 같은 시기 (11-11) */
// 가격 예측은 가짜 값으로 대신하지 않는다 (11-13): ML API 가 안 되면 오류를 보여 줌
export const predict = (req) =>
  withFallback(() => request(ML_API_BASE, "/predict", { method: "POST", body: req }), () => {
    throw new Error("AI 예측 서버에 연결할 수 없어요. 잠시 뒤 다시 시도해 주세요.");
  });

/** 로그인 없이 보는 미리보기 (11-17): 전국 평균 7일 · 4주만. 시장·품종·날짜를 고르는 predict 는 서버가 회원만 통과시킴 */
export const previewPredict = (item, horizon = 28) =>
  withFallback(() => request(ML_API_BASE, `/public/predict?item=${encodeURIComponent(item)}&horizon=${horizon}`), () => {
    throw new Error("AI 예측 서버에 연결할 수 없어요. 잠시 뒤 다시 시도해 주세요.");
  });

/** 로그인 없이 보는 미리보기 (11-17): 오늘 1,200평에 심으면 순수익 위 3개 */
export const previewRecommend = (region, type) =>
  withFallback(() => request(ML_API_BASE, `/public/recommend?region=${encodeURIComponent(region)}&type=${encodeURIComponent(type)}`), noMock);

export const getTopMovers = ({ horizon = 7, limit = 4 } = {}) =>
  withFallback(
    () => request(ML_API_BASE, `/predict/top-movers?horizon=${horizon}&limit=${limit}`),
    noMock, // 11-17: 가짜 급등락 값으로 대신하지 않음 (지금 화면에서는 안 쓰는 함수)
  );

function noMock() { throw new Error("AI 서버에 연결할 수 없어요. 잠시 뒤 다시 시도해 주세요."); }

// ── 작물 추천 (docs/06_api_spec.md 1-6) ──
// 작물 추천 (11-13): 실제 자료(shared/crops.json + DB 예측)로 계산 — 서버가 안 되면 가짜 값 대신 오류를 보여 줌
export const getRecommendCrops = () => withFallback(() => request(ML_API_BASE, "/recommend/crops"), noMock);

/** 내 땅으로 작물 고르기. @param {{lands: {type: string, area_pyeong: number}[], start_date: string}} req */
export const recommendCrops = (req) =>
  withFallback(() => request(ML_API_BASE, "/recommend/crops", { method: "POST", body: req }), noMock);

/** 작물로 가장 좋은 심는 날 고르기. @param {{crop: string, area_pyeong: number}} req */
export const recommendPlantingDates = (req) =>
  withFallback(() => request(ML_API_BASE, "/recommend/planting-dates", { method: "POST", body: req }), noMock);

/** 작물 정보 탭: 작형·수량·경영비 */
export const getCropInfo = (code) => withFallback(() => request(ML_API_BASE, `/recommend/crops/${code}`), noMock);

/** 작물의 앞으로 12개월 예상 도매가 (주 단위 53점, 11-11) */
export const getCropPricePath = (code) =>
  withFallback(() => request(ML_API_BASE, `/recommend/crops/${code}/prices`), noMock);

/** 개발자 페이지: 응답 속도까지 재는 상태 확인 */
export async function pingMl() {
  const t0 = performance.now();
  try {
    const data = await request(ML_API_BASE, "/health", { timeoutMs: 3000 });
    if (!data?.status) throw new Error("ML API 가 아닌 응답이 왔어요 (주소 설정 확인)"); // 11-17: JSON 이 아닌 응답이면 대시보드가 죽었음
    return { ok: true, ms: Math.round(performance.now() - t0), detail: data };
  } catch (e) {
    return { ok: false, ms: null, detail: e.message };
  }
}
