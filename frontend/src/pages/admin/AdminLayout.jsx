import { NavLink, Outlet } from "react-router-dom";
import { resetAll } from "../../mocks/store";

const MENU = [
  ["system", "🖥️ 서버·API 상태"],
  ["data", "📥 데이터 수집 현황"],
  ["model", "📈 모델 성능"],
  ["reports", "🚨 신고·분쟁"],
  ["notices", "📢 공지사항"],
  ["members", "👥 회원·경매 관리"],
];

export default function AdminLayout() {
  return (
    <div className="page">
      <div className="page-head">
        <h1>개발자 페이지</h1>
        <p>서비스 운영·모니터링 도구 (관리자 전용)</p>
      </div>
      <div className="admin-layout">
        <nav className="admin-nav">
          {MENU.map(([to, label]) => (
            <NavLink key={to} to={to}>{label}</NavLink>
          ))}
          <button
            className="btn sm danger"
            style={{ marginTop: 16 }}
            onClick={() => {
              if (confirm("가짜 데이터(회원가입·입찰·공지·신고 처리 기록)를 처음 상태로 되돌릴까요?")) {
                resetAll();
                location.href = "/admin";
              }
            }}
          >
            데모 데이터 초기화
          </button>
        </nav>
        <div style={{ display: "grid", gap: 20, minWidth: 0 }}>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
