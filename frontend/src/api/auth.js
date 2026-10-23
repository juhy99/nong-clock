// 회원가입·로그인 (Spring 담당). 두 가지 방식 중 하나로 동작한다 (VITE_AUTH):
//   mock (기본)  브라우저에 저장되는 가짜 계정. 서버 사이트도 백엔드가 준비될 때까지 이 방식
//   spring       백엔드(backend-spring)의 /api/auth/... 에 연결. 백엔드에 아직 없는 기능(내 정보 수정·비밀번호 변경·탈퇴)은 "준비 중" 오류
// ⚠️ 실제 서비스에서는 비밀번호를 프론트에 저장하지 않는다. Spring 이 암호화 저장 + 토큰(JWT 등) 발급을 맡는다.
import axios from "axios";
import { fake } from "./client";
import { auctionsDb, usersDb } from "../mocks/auctions";
import { load, save } from "../mocks/store";

export const AUTH_MODE = import.meta.env.VITE_AUTH === "spring" ? "spring" : "mock";
const SPRING = AUTH_MODE === "spring";

const publicUser = ({ password, ...u }) => u;

export const getSession = () => load("session", null);

export function login(email, password) {
  if (SPRING) return springLogin(email, password);
  const u = usersDb.all().find((x) => x.email === email.trim().toLowerCase());
  if (!u || u.password !== password) return Promise.reject(new Error("이메일 또는 비밀번호가 맞지 않습니다"));
  if (u.status === "탈퇴") return Promise.reject(new Error("탈퇴한 계정입니다"));
  if (u.status === "정지") return Promise.reject(new Error("이용이 정지된 계정입니다. 고객센터에 문의하세요"));
  const session = publicUser(u);
  save("session", session);
  return fake(session);
}

export function logout() {
  save("session", null);
}

/** 가입 화면에서 입력하는 동안 확인. spring 은 확인 API 가 없어 가입 버튼을 누른 뒤 백엔드 오류로 알린다 */
export function isEmailTaken(email) {
  if (SPRING) return false;
  return usersDb.all().some((x) => x.email === email.trim().toLowerCase());
}

/** 회원 유형 선택 없음: 모든 회원이 입찰·판매 가능 (farm_name 은 선택, 경매 판매자 이름으로 표시)
 * @param {{email, password, name, phone, region, farm_name?, marketing?: boolean}} form */
export function signup(form) {
  if (SPRING) return springSignup(form);
  const rows = usersDb.all();
  const email = form.email.trim().toLowerCase();
  if (rows.some((x) => x.email === email)) return Promise.reject(new Error("이미 가입된 이메일입니다"));
  const user = {
    id: `u${Date.now()}`,
    email,
    password: form.password,
    name: form.name.trim(),
    phone: form.phone,
    type: "member",
    region: form.region,
    farm_name: form.farm_name || "",
    marketing: !!form.marketing,
    status: "정상",
    joined: new Date().toISOString().slice(0, 10),
  };
  rows.push(user);
  usersDb.saveAll(rows);
  const session = publicUser(user);
  save("session", session);
  return fake(session);
}

// ── 내 정보 수정·탈퇴 ──

function updateUser(id, fn) {
  const rows = usersDb.all();
  const u = rows.find((x) => x.id === id);
  if (!u) throw new Error("회원 정보를 찾을 수 없습니다");
  fn(u);
  usersDb.saveAll(rows);
  const session = publicUser(u);
  save("session", session);
  return session;
}

/** 이메일·회원 유형은 바꿀 수 없다. favorites(관심 품목), notify(알림 종류별 받기) 포함 */
export function updateProfile(id, patch) {
  if (SPRING) return springUpdateProfile(patch);
  const { name, phone, region, farm_name, favorites, notify } = patch;
  const allowed = Object.fromEntries(Object.entries({ name, phone, region, farm_name, favorites, notify }).filter(([, v]) => v !== undefined));
  return fake(updateUser(id, (u) => Object.assign(u, allowed)));
}

export function changePassword(id, current, next) {
  if (SPRING) return notReady("비밀번호 변경");
  const u = usersDb.all().find((x) => x.id === id);
  if (!u || u.password !== current) return Promise.reject(new Error("현재 비밀번호가 맞지 않습니다"));
  if (next.length < 8 || !/[A-Za-z]/.test(next) || !/\d/.test(next)) return Promise.reject(new Error("새 비밀번호는 영문과 숫자를 섞어 8자 이상이어야 합니다"));
  updateUser(id, (x) => (x.password = next));
  return fake(true);
}

/** 탈퇴를 막는 이유 목록. 비어 있으면 탈퇴 가능 */
export function withdrawBlockers(id) {
  if (SPRING) return []; // 경매가 아직 가짜 데이터라 확인할 수 없음 (백엔드 DELETE /api/me 가 409 로 알려줄 예정)
  const now = new Date();
  const live = (a) => (a.status === "진행중" && new Date(a.ends_at) > now) || a.status === "승인대기";
  const rows = auctionsDb.all();
  const reasons = [];
  const selling = rows.filter((a) => a.seller === id && live(a)).length;
  if (selling) reasons.push(`진행 중이거나 승인 대기 중인 내 경매 ${selling}건`);
  const leading = rows.filter((a) => live(a) && a.bids.some((b) => !b.cancelled && b.user === id && b.amount === a.current_bid)).length;
  if (leading) reasons.push(`최고가로 입찰 중인 경매 ${leading}건`);
  return reasons;
}

/**
 * 회원 탈퇴. 거래 기록이 깨지지 않도록 정보를 지우지 않고 "탈퇴" 상태로 바꾼다(소프트 삭제).
 * 실제로는 개인정보(이름·연락처)는 법정 보관 기간 뒤 Spring 이 지운다.
 */
export function withdraw(id, password) {
  if (SPRING) return notReady("회원 탈퇴");
  const u = usersDb.all().find((x) => x.id === id);
  if (!u || u.password !== password) return Promise.reject(new Error("비밀번호가 맞지 않습니다"));
  const blockers = withdrawBlockers(id);
  if (blockers.length) return Promise.reject(new Error(`${blockers.join(", ")}이 있어 탈퇴할 수 없습니다`));
  updateUser(id, (x) => Object.assign(x, { status: "탈퇴", withdrawn_at: new Date().toISOString() }));
  save("session", null);
  return fake(true);
}

// ── spring: 백엔드 연결 (docs/06_api_spec.md 2장) ──
// 서버 화면은 nginx 가 /api/ 를 backend 컨테이너로, 내 PC 의 npm run dev 는 Vite 가 SPRING_URL(기본 localhost:8080)로 넘긴다

const api = axios.create({ timeout: 8000 });

// 백엔드 값 → 화면이 쓰는 값 (예전 가짜 계정과 같은 모양)
const USER_TYPE = { MEMBER: "member", ADMIN: "admin" };
const USER_STATUS = { ACTIVE: "정상", SUSPENDED: "정지", WITHDRAWN: "탈퇴" };

function fromSpring(u) {
  if (!u || typeof u !== "object" || !u.email) throw new Error("백엔드 응답에 회원 정보가 없습니다");
  const { password, passwordHash, farmName, type, status, ...rest } = u; // 비밀번호(해시)는 브라우저에 남기지 않는다
  return {
    ...rest,
    farm_name: farmName ?? rest.farm_name ?? "",
    type: USER_TYPE[String(type ?? "MEMBER").toUpperCase()] ?? "member",
    status: USER_STATUS[status] ?? status ?? "정상",
  };
}

/** 백엔드 오류 → 화면에 보여줄 문장 (Spring 은 오류 문장을 글자 그대로 돌려준다) */
function springError(e, fallback) {
  const data = e.response?.data;
  if (typeof data === "string" && data.trim()) return new Error(data.trim());
  if (data?.message) return new Error(data.message);
  if (!e.response) return new Error("회원 서버에 연결할 수 없습니다. 잠시 뒤 다시 시도하세요");
  return new Error(fallback);
}

async function springLogin(email, password) {
  let user;
  try {
    const res = await api.post("/api/auth/login", { email: email.trim().toLowerCase(), password });
    user = fromSpring(res.data);
  } catch (e) {
    throw e.response || e.request ? springError(e, "이메일 또는 비밀번호가 맞지 않습니다") : e;
  }
  // 백엔드가 막아야 하는 것이지만, 아직 막지 않는 동안 화면에서라도
  if (user.status === "탈퇴") throw new Error("탈퇴한 계정입니다");
  if (user.status === "정지") throw new Error("이용이 정지된 계정입니다. 고객센터에 문의하세요");
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
      name: form.name.trim(),
      phone: form.phone,
      region: form.region,
      farmName: form.farm_name || "",
      marketing: !!form.marketing,
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

// 백엔드에 PATCH /api/me 가 생기기 전: 관심 품목만 이 브라우저의 로그인 정보에 저장 (내 화면에만 쓰임). 나머지는 준비 중
function springUpdateProfile(patch) {
  const keys = Object.keys(patch).filter((k) => patch[k] !== undefined);
  if (!keys.length || keys.some((k) => k !== "favorites")) return notReady("내 정보 수정");
  const session = { ...getSession(), favorites: patch.favorites };
  save("session", session);
  return fake(session, 0);
}

const notReady = (what) => Promise.reject(new Error(`${what} 기능은 아직 준비 중이에요 (회원 백엔드 연결 중)`));
