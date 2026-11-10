import { useState } from "react";
import { getUsers } from "../../api/admin";
import { USER_TYPE_LABEL } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";

export default function Members() {
  const users = useAsync(getUsers);
  const [q, setQ] = useState("");

  return (
    <section className="card">
      <SectionHead
        title="회원 관리"
        desc="탈퇴한 회원은 목록에서 바로 지워집니다 (정지 기능 없음)"
        right={<input className="input" style={{ maxWidth: 200 }} placeholder="이름·이메일 검색" value={q} onChange={(e) => setQ(e.target.value)} />}
      />
      <Async state={users}>
        {(rows) => (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>이름</th><th>이메일</th><th>유형</th><th>지역</th><th>가입일</th></tr>
              </thead>
              <tbody>
                {rows.filter((u) => `${u.name}${u.email}`.includes(q.trim())).map((u) => (
                  <tr key={u.id}>
                    <td><b>{u.name}</b>{u.farm_name && <div className="muted small">{u.farm_name}</div>}</td>
                    <td className="small">{u.email}</td>
                    <td className="small">{USER_TYPE_LABEL[u.type]}</td>
                    <td className="small">{u.region}</td>
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
