import { useState } from "react";
import { Link } from "react-router-dom";
import { STATUS_BADGE, cancelMyAuction, displayStatus, getMyAuctions } from "../../api/auction";
import { useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";
import Photo from "../../components/Photo";
import { useNow } from "../Auctions";
import { remain, won } from "../../utils/format";

export default function MyAuctions() {
  const { user } = useAuth();
  const state = useAsync(() => getMyAuctions(user.id), [user.id]);
  const now = useNow();
  const [msg, setMsg] = useState("");

  async function cancel(a) {
    if (!confirm(`'${a.title}' 경매를 취소할까요?`)) return;
    try {
      await cancelMyAuction(user, a.id);
      setMsg("");
      state.reload();
    } catch (e) {
      setMsg(e.message);
    }
  }

  return (
    <section className="card">
      <Async state={state} empty={<>아직 등록한 경매가 없습니다. <Link className="link" to="/mypage/auctions/new">첫 경매 등록하기 →</Link></>}>
        {(rows) => {
          const count = (s) => rows.filter((a) => displayStatus(a, now) === s).length;
          return (
            <>
              <SectionHead
                title="내가 등록한 경매"
                desc={`진행 중 ${count("진행중")} · 승인 대기 ${count("승인대기")} · 낙찰 ${count("낙찰")}`}
                right={<Link className="btn primary sm" to="/mypage/auctions/new">＋ 새 경매 등록</Link>}
              />
              {msg && <p className="hint error">{msg}</p>}
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr><th>상품</th><th className="r">시작가</th><th className="r">현재가</th><th className="r">입찰</th><th>남은 시간</th><th>상태</th><th /></tr>
                  </thead>
                  <tbody>
                    {rows.map((a) => {
                      const st = displayStatus(a, now);
                      return (
                        <tr key={a.id}>
                          <td>
                            <Link className="link row-title" to={`/auctions/${a.id}`}>
                              {a.images?.length ? <Photo src={a.images[0]} alt="" className="mini-photo" /> : a.emoji} {a.title}
                            </Link>
                          </td>
                          <td className="r num">{won(a.start_price)}원</td>
                          <td className="r num"><b>{won(a.current_bid)}원</b></td>
                          <td className="r">{a.bid_count}건</td>
                          <td className={st === "진행중" ? "timer" : "muted"}>{st === "진행중" ? remain(new Date(a.ends_at) - now) : "-"}</td>
                          <td><span className={`badge ${STATUS_BADGE[st] ?? ""}`}>{st}</span></td>
                          <td className="r">
                            {(st === "진행중" || st === "승인대기") && a.bid_count === 0 && (
                              <button className="btn sm danger" onClick={() => cancel(a)}>취소</button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="hint" style={{ marginBottom: 0 }}>새 경매는 관리자 승인 후 경매 마켓에 나와요. 입찰이 들어온 경매는 취소할 수 없어요.</p>
            </>
          );
        }}
      </Async>
    </section>
  );
}
