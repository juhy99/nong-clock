// 회원 신고 (Spring 담당). 경매·게시글·댓글을 신고할 수 있다. 관리자 처리 화면은 api/admin.js 의 getReports / processReport.
import { fake } from "./client";
import { notify } from "./notify";
import { INITIAL_REPORTS } from "../mocks/admin";
import { commentsDb, postsDb } from "../mocks/board";
import { load, save } from "../mocks/store";

const OPEN = ["접수", "검토중"];

/** 신고 대상의 작성자 (글·댓글이면 작성자, 경매면 판매자). 실제로는 Spring 이 DB 에서 찾는다. */
function ownerOf(kind, id) {
  if (kind === "post") return postsDb.all().find((p) => p.id === id)?.author;
  if (kind === "comment") return commentsDb.all().find((c) => c.id === id)?.author;
  return null;
}

/**
 * 신고하기.
 * - 경매: { kind: "auction", target_id: 경매번호, target_label: 경매 제목, type, reason, bidder?, bidder_label? }
 * - 게시글·댓글: { kind: "post" | "comment", target_id, target_label, post_id, type, reason }
 * 회원 화면에는 가려진 아이디(bidder_label)만 보이고, 관리자는 실제 아이디(bidder)로 확인한다.
 */
export function submitReport(user, form) {
  if (!user) return Promise.reject(new Error("로그인 후 신고할 수 있습니다"));
  if (form.reason.trim().length < 5) return Promise.reject(new Error("신고 내용을 5자 이상 적어주세요"));
  const target_user = ownerOf(form.kind, form.target_id);
  if (target_user === user.id) return Promise.reject(new Error("내가 쓴 글·댓글은 신고할 수 없습니다"));
  const rows = load("reports", INITIAL_REPORTS);
  const kind = (r) => r.kind ?? "auction";
  const targetId = (r) => r.target_id ?? r.auction_id;
  if (rows.some((r) => r.reporter === user.id && kind(r) === form.kind && targetId(r) === form.target_id && OPEN.includes(r.status)))
    return Promise.reject(new Error("이미 신고해서 처리 중인 대상입니다"));

  const what = { auction: "경매", post: "게시글", comment: "댓글" }[form.kind];
  const bidder = form.kind === "auction" && form.bidder ? ` · 입찰자 ${form.bidder_label ?? form.bidder}` : "";
  const r = {
    id: Math.max(100, ...rows.map((x) => x.id)) + 1,
    kind: form.kind,
    type: form.type,
    target: `${what} #${form.target_id} ${form.target_label}${bidder}`,
    target_id: form.target_id,
    auction_id: form.kind === "auction" ? form.target_id : undefined,
    post_id: form.kind === "auction" ? undefined : form.post_id,
    target_user,
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
