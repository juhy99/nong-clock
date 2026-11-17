import { useState } from "react";
import { adminUsers } from "../../api/adminBoard";
import { Async, SectionHead, useAsync } from "../../components/common";
import { won } from "../../utils/format";

/** 회원 관리 (11-17): 예시 데이터 → 실제 DB 회원 (Spring GET /api/admin/users). 보기만, 전화번호는 안 보여 줌 */

export default function Members() {
  const users = useAsync(adminUsers);
  const [q, setQ] = useState("");

  return (
    <section className="card">
      <SectionHead
        title="회원 관리"
        desc={`실제 가입 회원${users.data ? ` ${won(users.data.length)}명` : ""} · 최근 가입 순 · 탈퇴한 회원은 목록에서 바로 지워져요 (정지 기능 없음)`}
        right={<input className="input" style={{ maxWidth: 200 }} placeholder="닉네임·이메일 검색" value={q} onChange={(e) => setQ(e.target.value)} />}
      />
      <Async state={users}>
        {(rows) => (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>닉네임</th><th>이메일</th><th>지역</th><th className="num">글</th><th className="num">댓글</th><th>가입일</th></tr>
              </thead>
              <tbody>
                {rows.filter((u) => `${u.nickname}${u.email}`.toLowerCase().includes(q.trim().toLowerCase())).map((u) => (
                  <tr key={u.id}>
                    <td><b>{u.nickname}</b>{u.farmName && <div className="muted small">{u.farmName}</div>}</td>
                    <td className="small">{u.email}</td>
                    <td className="small">{u.region ?? "-"}</td>
                    <td className="small num">{u.posts}</td>
                    <td className="small num">{u.comments}</td>
                    <td className="small num">{u.joined}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Async>
    </section>
  );
}
