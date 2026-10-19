import { Fragment, useState } from "react";
import { getReports, processReport } from "../../api/admin";
import { REPORT_STATUSES } from "../../mocks/admin";
import { Async, SectionHead, useAsync } from "../../components/common";
import { dateTime } from "../../utils/format";
import BidCancelPanel from "./BidCancelPanel";

const TYPE_BADGE = { 허위매물: "amber", 사기의심: "red", 부정입찰: "blue", 기타: "" };
const STATUS_BADGE = { 접수: "red", 검토중: "amber", 처리완료: "green", 반려: "" };

export default function Reports() {
  const state = useAsync(getReports);
  const [filter, setFilter] = useState("전체");
  const [open, setOpen] = useState(null);
  const [memo, setMemo] = useState("");
  const [notifyReporter, setNotifyReporter] = useState(true);

  async function change(r, status) {
    await processReport(r.id, { status, memo, notifyReporter });
    setOpen(null);
    state.reload();
  }

  return (
    <section className="card">
      <SectionHead title="신고 및 분쟁 관리" desc="허위 매물 · 사기 의심 · 부정 입찰 신고 접수 및 처리" />
      <Async state={state} empty="접수된 신고가 없습니다">
        {(rows) => {
          const counts = Object.fromEntries(REPORT_STATUSES.map((s) => [s, rows.filter((r) => r.status === s).length]));
          const shown = filter === "전체" ? rows : rows.filter((r) => r.status === filter);
          return (
            <>
              <div className="pills" style={{ marginBottom: 14 }}>
                {["전체", ...REPORT_STATUSES].map((s) => (
                  <button key={s} className={`pill ${filter === s ? "on" : ""}`} onClick={() => setFilter(s)}>
                    {s} {s === "전체" ? rows.length : counts[s]}
                  </button>
                ))}
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>#</th><th>유형</th><th>대상</th><th>신고자</th><th>접수</th><th>상태</th><th /></tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => (
                      <Fragment key={r.id}>
                        <tr>
                          <td className="muted">{r.id}</td>
                          <td><span className={`badge ${TYPE_BADGE[r.type]}`}>{r.type}</span></td>
                          <td>{r.target}</td>
                          <td className="small">{r.reporter}</td>
                          <td className="small num">{dateTime(r.created_at)}</td>
                          <td><span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status}</span></td>
                          <td className="r">
                            <button className="btn sm" onClick={() => { setOpen(open === r.id ? null : r.id); setMemo(r.memo); setNotifyReporter(true); }}>
                              {open === r.id ? "닫기" : "처리"}
                            </button>
                          </td>
                        </tr>
                        {open === r.id && (
                          <tr>
                            <td colSpan={7} style={{ background: "#fafaf7" }}>
                              <div style={{ display: "grid", gap: 10 }}>
                                <div>
                                  <b>신고 내용</b>
                                  <div>{r.reason}</div>
                                  {r.bidder && <div className="muted small">지목한 입찰자: {r.bidder}</div>}
                                </div>
                                {r.auction_id && (
                                  <div className="card" style={{ padding: 14 }}>
                                    <BidCancelPanel auctionId={r.auction_id} />
                                  </div>
                                )}
                                <div className="field">
                                  <label>처리 결과 (신고자에게 그대로 전달됩니다)</label>
                                  <textarea className="input" rows={2} value={memo} onChange={(e) => setMemo(e.target.value)} placeholder="확인 내용, 조치 사항 등" />
                                </div>
                                <label className="check">
                                  <input type="checkbox" checked={notifyReporter} onChange={(e) => setNotifyReporter(e.target.checked)} />
                                  신고자에게 처리 결과 알림 보내기
                                </label>
                                <div className="pills">
                                  {REPORT_STATUSES.filter((s) => s !== "접수").map((s) => (
                                    <button key={s} className="btn sm" onClick={() => change(r, s)}>{s}(으)로 변경</button>
                                  ))}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          );
        }}
      </Async>
    </section>
  );
}
