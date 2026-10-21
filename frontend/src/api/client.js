// API 주소는 이 파일 한 곳에서만 관리한다.
// 지금: ML API(FastAPI) 직접 호출 → 나중에 Spring 중계가 생기면 .env 의 주소만 바꾼다.
export const ML_API_BASE = import.meta.env.VITE_ML_API_BASE || "http://localhost:8000";

// 데이터 출처. mock: 가짜 데이터(기본) · live: 내 PC 테스트용으로 기상청·네이버를 직접 부른다.
// live 는 Vite 개발 서버(npm run dev)가 키를 붙여 중계해 줄 때만 동작한다. 빌드한 배포본에서는 항상 mock.
export const DATA_SOURCE = import.meta.env.DEV && import.meta.env.VITE_DATA_SOURCE === "live" ? "live" : "mock";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function request(base, path, { method = "GET", body, timeoutMs = 8000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}${path}`, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = typeof data?.detail === "string" ? data.detail : `HTTP ${res.status}`;
      throw new ApiError(detail, res.status);
    }
    return data;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(e.name === "AbortError" ? "응답 시간 초과" : "서버에 연결할 수 없습니다", 0);
  } finally {
    clearTimeout(timer);
  }
}

/** 아직 서버가 없는 기능(Spring 담당)의 가짜 응답. 실제 API처럼 약간 늦게 돌려준다. */
export const fake = (data, delayMs = 250) =>
  new Promise((resolve) => setTimeout(() => resolve(structuredClone(data)), delayMs));

/** 테스트 모드: Vite 개발 서버의 /live/... 중계 주소 호출. 공공데이터포털은 오류를 XML 로 줄 때가 있어 글로 받아 본다. */
export async function liveGet(path, { timeoutMs = 15000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(path, { signal: ctrl.signal });
    const text = await res.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch {
      const msg = text.match(/<(returnAuthMsg|errMsg|resultMsg)>([^<]+)</)?.[2];
      if (msg) throw new ApiError(`API 오류: ${msg}`, res.status);
      throw new ApiError(text ? `API 응답을 읽을 수 없습니다 (HTTP ${res.status})` : "외부 API 에 연결하지 못했습니다 (인터넷 연결 확인)", res.status);
    }
    if (!res.ok) throw new ApiError(`API 오류: ${data?.errorMessage ?? data?.message ?? `HTTP ${res.status}`}`, res.status);
    return data;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(e.name === "AbortError" ? "응답 시간 초과" : "테스트 모드 중계에 연결할 수 없습니다 (npm run dev 로 실행했는지 확인)", 0);
  } finally {
    clearTimeout(timer);
  }
}
