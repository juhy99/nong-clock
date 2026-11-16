// 회원가입·로그인 (Spring 담당, 11-14: 가짜 계정 없앰 — 언제나 백엔드 backend-spring 의 /api/auth/... 에 연결, 서버가 안 되면 오류 안내)
// 비밀번호는 서버가 BCrypt 로 암호화 저장. 로그인 상태는 서버 세션 + 브라우저의 세션 쿠키(HttpOnly, JS 로 못 읽음) (11-10).
//   아래 "session"(localStorage)은 화면 표시용 복사본일 뿐이고, 새로고침 때 GET /api/me 로 서버에 다시 확인한다 (refreshSession).
// 관리자는 회원이 아님: DB 표 admin 의 따로 된 계정으로 관리자 사이트에서만 로그인 (api/adminBoard.js, 11-14)
// 마이페이지(11-16): 내 정보 수정 PATCH /api/me · 비밀번호 PUT /api/me/password · 관심 품목 PUT /api/me/favorites (DB user_favorite)
import axios from "axios";
import { load, save } from "../mocks/store";

export const getSession = () => load("session", null);

export const login = (email, password) => springLogin(email, password);

export function logout() {
  api.post("/api/auth/logout").catch(() => {}); // 서버 세션 끊기 (실패해도 화면은 로그아웃)
  save("session", null);
}

/** 새로고침·첫 화면에서 "지금 로그인돼 있나?"를 서버에 확인. 세션이 끝났으면 화면의 로그인 정보도 지움 */
export async function refreshSession() {
  try {
    const res = await api.get("/api/me");
    const prev = getSession();
    let user = fromSpring(res.data);
    // 11-16: 관심 품목은 서버(DB)에 저장. 예전에 이 브라우저에만 저장해 둔 관심 품목이 있고 서버에는 없으면 한 번 옮김
    if (!user.favorites.length && prev?.id === user.id && prev.favorites?.length) {
      user = { ...user, favorites: await putFavorites(prev.favorites).catch(() => prev.favorites) };
    }
    save("session", user);
    return user;
  } catch (e) {
    if (e.response?.status === 401 || e.response?.status === 403) { // 403: 같은 브라우저에서 관리자로 로그인한 세션 (11-14)
      save("session", null);
      return null;
    }
    return getSession(); // 서버에 연결이 안 되면 일단 지금 화면 상태 유지
  }
}

/** [중복 확인] 버튼: 이메일·닉네임이 이미 쓰이는지 (GET /api/auth/check?email=|nickname=) */
export function checkDuplicate(kind, value) {
  return api.get("/api/auth/check", { params: { [kind]: value.trim() } }).then((r) => !!r.data?.taken, (e) => Promise.reject(springError(e, "중복 확인을 하지 못했습니다")));
}

/** 회원 유형 선택 없음: 모든 회원이 같은 일반회원 (farm_name 은 선택)
 * @param {{email, password, name, phone, region, farm_name?}} form  (마케팅 동의는 받지 않음, 11-11) */
export const signup = (form) => springSignup(form);

// ── 내 정보 수정·탈퇴 ──

/** 내 정보 수정 (11-16). patch 가 관심 품목(favorites)만이면 PUT /api/me/favorites, 아니면 PATCH /api/me (이메일은 못 바꿈) */
export const updateProfile = (id, patch) => springUpdateProfile(patch);

/** 비밀번호 변경 (11-16): PUT /api/me/password {current, next}. 지금 비밀번호가 틀리면 403 */
export async function changePassword(id, current, next) {
  try {
    await api.put("/api/me/password", { current, next });
  } catch (e) {
    throw springError(e, "비밀번호를 바꾸지 못했습니다");
  }
  return true;
}

/** 탈퇴를 막는 이유 목록. 경매가 보류 중이라 늘 비어 있음 (경매를 다시 켜면 서버 DELETE /api/me 가 409 로 알려줄 예정) */
export const withdrawBlockers = () => [];

/**
 * 회원 탈퇴 (11-10 결정): 회원 정보와 그 회원이 쓴 글·댓글을 지운다. 되돌릴 수 없음. 정지 기능은 없음.
 * DELETE /api/me {password} → 서버가 비밀번호 확인 뒤 DB 에서 삭제하고 세션을 끊음
 */
export async function withdraw(id, password) {
  try {
    await api.delete("/api/me", { data: { password } });
  } catch (e) {
    throw springError(e, "탈퇴하지 못했습니다");
  }
  save("session", null);
  return true;
}

// ── spring: 백엔드 연결 (docs/06_api_spec.md 2장) ──
// 서버 화면은 nginx 가 /api/ 를 backend 컨테이너로, 내 PC 의 npm run dev 는 Vite 가 SPRING_URL(기본 localhost:8080)로 넘긴다

const api = axios.create({ timeout: 8000 });

// 백엔드 값 → 화면이 쓰는 값
const USER_TYPE = { MEMBER: "member", ADMIN: "admin" };

function fromSpring(u) {
  if (!u || typeof u !== "object" || !u.email) throw new Error("백엔드 응답에 회원 정보가 없습니다");
  const { password, passwordHash, farmName, type, ...rest } = u; // 비밀번호(해시)는 브라우저에 남기지 않는다
  return {
    ...rest,
    favorites: Array.isArray(rest.favorites) ? rest.favorites : [],
    farm_name: farmName ?? rest.farm_name ?? "",
    type: USER_TYPE[String(type ?? "MEMBER").toUpperCase()] ?? "member",
  };
}

/** 백엔드 오류 → 화면에 보여줄 문장 + 응답 코드(status, 서버에 못 닿으면 0). 오류 팝업(ErrorPopup)이 status 로 설명을 고른다 */
function springError(e, fallback) {
  const data = e.response?.data;
  const text = typeof data === "string" && data.trim() ? data.trim() : data?.message;
  const err = new Error(text || (e.response ? fallback : "회원 서버에 연결할 수 없습니다"));
  err.status = e.response?.status ?? 0;
  return err;
}

async function springLogin(email, password) {
  let user;
  try {
    const res = await api.post("/api/auth/login", { email: email.trim().toLowerCase(), password });
    user = fromSpring(res.data);
  } catch (e) {
    throw e.response || e.request ? springError(e, "이메일 또는 비밀번호가 맞지 않습니다") : e;
  }
  save("session", user);
  return user;
}

async function springSignup(form) {
  const email = form.email.trim().toLowerCase();
  let data;
  try {
    const res = await api.post("/api/auth/signup", {
      email,
      password: form.password,
      nickname: (form.nickname ?? form.name).trim(),
      name: form.name.trim(),
      phone: form.phone,
      region: form.region,
      farmName: form.farm_name || "",
      });
    data = res.data;
  } catch (e) {
    throw springError(e, "회원가입에 실패했습니다");
  }
  // 가입 응답에 회원 정보가 있으면 그대로, 없으면(완료 문장만 오면) 바로 로그인해 가입 직후 로그인 상태로
  if (data && typeof data === "object" && data.email) {
    const user = fromSpring(data);
    save("session", user);
    return user;
  }
  return springLogin(email, form.password);
}

/** 관심 품목 전체 저장 → 서버에 저장된 목록 */
async function putFavorites(items) {
  try {
    return (await api.put("/api/me/favorites", { items })).data;
  } catch (e) {
    throw springError(e, "관심 품목을 저장하지 못했습니다");
  }
}

// 11-16: 내 정보 수정은 PATCH /api/me, 관심 품목만 바꿀 때는 PUT /api/me/favorites. 결과를 화면 로그인 정보에도 반영
async function springUpdateProfile(patch) {
  const keys = Object.keys(patch).filter((k) => patch[k] !== undefined && k !== "notify"); // 알림 설정은 숨긴 기능 (서버에 안 보냄)
  if (keys.length === 1 && keys[0] === "favorites") {
    const session = { ...getSession(), favorites: await putFavorites(patch.favorites) };
    save("session", session);
    return session;
  }
  let user;
  try {
    const res = await api.patch("/api/me", { nickname: patch.name?.trim(), phone: patch.phone, region: patch.region, farmName: patch.farm_name ?? "" });
    user = fromSpring(res.data);
  } catch (e) {
    throw springError(e, "내 정보를 저장하지 못했습니다");
  }
  save("session", user);
  return user;
}
