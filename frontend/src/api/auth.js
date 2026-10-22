import axios from 'axios';
import { load, save } from "../mocks/store";

// 백엔드 서버 기본 주소 (Spring Boot 포트)
const API_BASE_URL = "http://localhost:8080";

const publicUser = ({ password, ...u }) => u;

export const getSession = () => load("session", null);

/** 실제 백엔드 로그인 API 연동 */
export async function login(email, password) {
  try {
    const response = await axios.post(`${API_BASE_URL}/login`, {
      email: email.trim().toLowerCase(),
      password: password
    });
    
    // 백엔드에서 받아온 사용자 정보를 세션에 저장
    const session = response.data;
    save("session", session);
    return session;
  } catch (error) {
    throw new Error(error.response?.data || "이메일 또는 비밀번호가 맞지 않습니다");
  }
}

export function logout() {
  save("session", null);
}

export function isEmailTaken(email) {
  // 실제 서비스에서는 백엔드 중복 확인 API를 호출해야 하지만, 
  // 우선 가입 과정에서 백엔드가 에러를 뱉도록 처리할 수 있습니다.
  return false; 
}

/** 실제 백엔드 회원가입 API 연동 (/register) */
export async function signup(form) {
  try {
    const response = await axios.post(`${API_BASE_URL}/register`, {
      email: form.email.trim().toLowerCase(),
      password: form.password,
      name: form.name.trim(),
      phone: form.phone,
      region: form.region,
      farmName: form.farm_name || "", // 백엔드 DTO 필드명에 맞춤
      marketing: !!form.marketing
    });

    return response.data;
  } catch (error) {
    throw new Error(error.response?.data || "회원가입에 실패했습니다.");
  }
}

// ── 내 정보 수정·탈퇴 등은 당장 쓰지 않는다면 기존 목 데이터 유지 혹은 추후 연동 ──
export function updateProfile(id, patch) {
  // 필요 시 백엔드 연동으로 변경 가능
  return Promise.resolve(patch);
}

export function changePassword(id, current, next) {
  return Promise.resolve(true);
}

export function withdrawBlockers(id) {
  return [];
}

export function withdraw(id, password) {
  save("session", null);
  return Promise.resolve(true);
}