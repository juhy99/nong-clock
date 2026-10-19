// 가짜 데이터 저장소. 회원가입·입찰·공지 작성 결과를 새로고침해도 유지하려고 브라우저 localStorage 에 둔다.
// Spring API 가 생기면 이 파일과 mocks/*.js 는 통째로 지우고 api/*.js 안쪽만 실제 호출로 바꾸면 된다.
const PREFIX = "farmbid-mock:";

export function load(key, initial) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    if (raw) return JSON.parse(raw);
  } catch {
    /* 저장소를 못 쓰는 환경이면 기본값 사용 */
  }
  return structuredClone(initial);
}

export function save(key, value) {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* 무시: 메모리에서만 유지 */
  }
}

/** 가짜 데이터 초기화 (개발자 페이지 버튼용) */
export function resetAll() {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith(PREFIX))
      .forEach((k) => localStorage.removeItem(k));
  } catch {
    /* 무시 */
  }
}
