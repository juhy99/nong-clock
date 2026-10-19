// 회원가입·로그인 (Spring 담당). 지금은 브라우저에 저장되는 가짜 계정으로 동작한다.
// ⚠️ 실제 서비스에서는 비밀번호를 프론트에 저장하지 않는다. Spring 이 암호화 저장 + 토큰(JWT 등) 발급을 맡는다.
import { fake } from "./client";
import { auctionsDb, usersDb } from "../mocks/auctions";
import { load, save } from "../mocks/store";

const publicUser = ({ password, ...u }) => u;

export const getSession = () => load("session", null);

export function login(email, password) {
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

export function isEmailTaken(email) {
  return usersDb.all().some((x) => x.email === email.trim().toLowerCase());
}

/** 회원 유형 선택 없음: 모든 회원이 입찰·판매 가능 (farm_name 은 선택, 경매 판매자 이름으로 표시)
 * @param {{email, password, name, phone, region, farm_name?, marketing?: boolean}} form */
export function signup(form) {
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
  const { name, phone, region, farm_name, favorites, notify } = patch;
  const allowed = Object.fromEntries(Object.entries({ name, phone, region, farm_name, favorites, notify }).filter(([, v]) => v !== undefined));
  return fake(updateUser(id, (u) => Object.assign(u, allowed)));
}

export function changePassword(id, current, next) {
  const u = usersDb.all().find((x) => x.id === id);
  if (!u || u.password !== current) return Promise.reject(new Error("현재 비밀번호가 맞지 않습니다"));
  if (next.length < 8 || !/[A-Za-z]/.test(next) || !/\d/.test(next)) return Promise.reject(new Error("새 비밀번호는 영문과 숫자를 섞어 8자 이상이어야 합니다"));
  updateUser(id, (x) => (x.password = next));
  return fake(true);
}

/** 탈퇴를 막는 이유 목록. 비어 있으면 탈퇴 가능 */
export function withdrawBlockers(id) {
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
  const u = usersDb.all().find((x) => x.id === id);
  if (!u || u.password !== password) return Promise.reject(new Error("비밀번호가 맞지 않습니다"));
  const blockers = withdrawBlockers(id);
  if (blockers.length) return Promise.reject(new Error(`${blockers.join(", ")}이 있어 탈퇴할 수 없습니다`));
  updateUser(id, (x) => Object.assign(x, { status: "탈퇴", withdrawn_at: new Date().toISOString() }));
  save("session", null);
  return fake(true);
}
