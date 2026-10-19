// 회원가입·로그인 (Spring 담당). 지금은 브라우저에 저장되는 가짜 계정으로 동작한다.
// ⚠️ 실제 서비스에서는 비밀번호를 프론트에 저장하지 않는다. Spring 이 암호화 저장 + 토큰(JWT 등) 발급을 맡는다.
import { fake } from "./client";
import { usersDb } from "../mocks/auctions";
import { load, save } from "../mocks/store";

const publicUser = ({ password, ...u }) => u;

export const getSession = () => load("session", null);

export function login(email, password) {
  const u = usersDb.all().find((x) => x.email === email.trim().toLowerCase());
  if (!u || u.password !== password) return Promise.reject(new Error("이메일 또는 비밀번호가 맞지 않습니다"));
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

/** @param {{email, password, name, phone, type: "buyer"|"seller", region, farm_name?, marketing?: boolean}} form */
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
    type: form.type,
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
