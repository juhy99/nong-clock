// 회원 신고 (Spring 담당). 관리자 처리 화면은 api/admin.js 의 getReports / processReport.
import { fake } from "./client";
import { notify } from "./notify";
import { INITIAL_REPORTS } from "../mocks/admin";
import { load, save } from "../mocks/store";

/**
 * 비정상 경매·입찰자 신고
 * 회원 화면에는 가려진 아이디(bidder_label)만 보이고, 관리자는 실제 아이디(bidder)로 확인한다.
 * @param {{type: string, auction_id: number, auction_title: string, bidder?: string, bidder_label?: string, reason: string}} form
 */
export function submitReport(user, form) {
  if (!user) return Promise.reject(new Error("로그인 후 신고할 수 있습니다"));
  if (form.reason.trim().length < 5) return Promise.reject(new Error("신고 내용을 5자 이상 적어주세요"));
  const rows = load("reports", INITIAL_REPORTS);
  const target = `경매 #${form.auction_id} ${form.auction_title}${form.bidder ? ` · 입찰자 ${form.bidder_label ?? form.bidder}` : ""}`;
  const r = {
    id: Math.max(100, ...rows.map((x) => x.id)) + 1,
    type: form.type,
    target,
    auction_id: form.auction_id,
    bidder: form.bidder || null,
    reporter: user.id,
    reason: form.reason.trim(),
    status: "접수",
    created_at: new Date().toISOString(),
    memo: "",
  };
  rows.push(r);
  save("reports", rows);
  notify(user.id, { type: "report", title: "신고 접수", body: `'${form.type}' 신고가 접수되었어요. 처리 결과를 알림으로 알려드릴게요.`, link: "/mypage?tab=reports" });
  return fake(r);
}

/** 내가 한 신고와 처리 결과 */
export const getMyReports = (userId) =>
  fake(load("reports", INITIAL_REPORTS).filter((r) => r.reporter === userId).sort((a, b) => b.id - a.id));
