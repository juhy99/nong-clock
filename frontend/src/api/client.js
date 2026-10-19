// API 주소는 이 파일 한 곳에서만 관리한다.
// 지금: ML API(FastAPI) 직접 호출 → 나중에 Spring 중계가 생기면 .env 의 주소만 바꾼다.
export const ML_API_BASE = import.meta.env.VITE_ML_API_BASE || "http://localhost:8000";

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
