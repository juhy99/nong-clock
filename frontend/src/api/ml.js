// ML API(FastAPI) 호출. 명세: docs/06_api_spec.md 1번 섹션.
// 서버가 꺼져 있으면 예비 데이터(mocks)로 대신 보여주고, 화면 상단에 "데모 데이터" 안내를 띄운다.
import { ML_API_BASE, request } from "./client";
import { HORIZONS, ITEMS, REGIONS } from "../mocks/catalog";
import { mockPredict, mockTopMovers } from "../mocks/prediction";

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

/** @param {{item: string, horizon: number, region?: string}} req */
export const predict = (req) =>
  withFallback(() => request(ML_API_BASE, "/predict", { method: "POST", body: req }), () => mockPredict(req));

export const getTopMovers = ({ horizon = 7, limit = 4 } = {}) =>
  withFallback(
    () => request(ML_API_BASE, `/predict/top-movers?horizon=${horizon}&limit=${limit}`),
    () => mockTopMovers(horizon, limit),
  );

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
