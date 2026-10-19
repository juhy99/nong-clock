import { useState } from "react";
import { getUsers, setUserStatus } from "../../api/admin";
import { USER_TYPE_LABEL, useAuth } from "../../components/AuthContext";
import { Async, SectionHead, useAsync } from "../../components/common";

const USER_BADGE = { 정상: "green", 정지: "red", 탈퇴: "" };

export default function Members() {
  const { user: me } = useAuth();
  const users = useAsync(getUsers);
  const [q, setQ] = useState("");

  return (
    <section className="card">
      <SectionHead
        title="회원 관리"
        desc="이용 정지된 회원은 로그인할 수 없습니다"
        right={<input className="input" style={{ maxWidth: 200 }} placeholder="이름·이메일 검색" value={q} onChange={(e) => setQ(e.target.value)} />}
      />
      <Async state={users}>
        {(rows) => (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th>이름</th><th>이메일</th><th>유형</th><th>지역</th><th>가입일</th><th>상태</th><th /></tr>
              </thead>
              <tbody>
                {rows.filter((u) => `${u.name}${u.email}`.includes(q.trim())).map((u) => (
                  <tr key={u.id}>
                    <td><b>{u.name}</b>{u.farm_name && <div className="muted small">{u.farm_name}</div>}</td>
                    <td className="small">{u.email}</td>
                    <td className="small">{USER_TYPE_LABEL[u.type]}</td>
                    <td className="small">{u.region}</td>
                    <td className="small num">{u.joined}</td>
                    <td><span className={`badge ${USER_BADGE[u.status] ?? ""}`}>{u.status}</span></td>
                    <td className="r">
                      {u.id !== me.id && u.status !== "탈퇴" && (
                        <button className="btn sm" onClick={async () => { await setUserStatus(u.id, u.status === "정상" ? "정지" : "정상"); users.reload(); }}>
                          {u.status === "정상" ? "이용 정지" : "정지 해제"}
                        </button>
                      )}
                    </td>
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
