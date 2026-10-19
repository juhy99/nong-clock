import { Link, useSearchParams } from "react-router-dom";
import { USER_TYPE_LABEL, useAuth } from "../../components/AuthContext";
import FavoriteAlerts, { FavoritePicker } from "./Favorites";
import MyAuctions from "./MyAuctions";
import MyBids from "./MyBids";
import MyNotifications from "./MyNotifications";
import MyReports from "./MyReports";
import Profile from "./Profile";

export default function MyPage() {
  const { user } = useAuth();
  const isSeller = user.type === "seller";
  const [params, setParams] = useSearchParams();
  const tabs = [
    ["watch", "관심 품목", FavoritePicker],
    ...(isSeller ? [["auctions", "내 경매", MyAuctions]] : []),
    ["bids", "입찰 참여", MyBids],
    ["notifications", "알림", MyNotifications],
    ["reports", "신고 내역", MyReports],
    ["profile", "내 정보", Profile],
  ];
  const tab = tabs.find(([k]) => k === params.get("tab")) ?? tabs[0];
  const Tab = tab[2];
  const go = (k) => setParams({ tab: k }, { replace: true });

  return (
    <div className="page">
      <section className="card profile">
        <div className="avatar">{isSeller ? "🧑‍🌾" : user.type === "admin" ? "🛠️" : "🧺"}</div>
        <div>
          <h2>
            {user.name} <span style={{ fontWeight: 500, fontSize: 15 }}>({user.email})</span>
          </h2>
          <div style={{ opacity: 0.85 }}>
            {USER_TYPE_LABEL[user.type]}
            {user.farm_name && ` · ${user.farm_name}`} · {user.region} · 가입 {user.joined}
          </div>
        </div>
        <div className="profile-actions">
          <button className="btn sm ghost" onClick={() => go("profile")}>내 정보 수정</button>
          {isSeller && <Link className="btn sm white" to="/mypage/auctions/new">＋ 경매 등록</Link>}
        </div>
      </section>
      <FavoriteAlerts onEdit={() => go("watch")} />
      <div className="tabs" role="tablist">
        {tabs.map(([k, label]) => (
          <button key={k} role="tab" className={tab[0] === k ? "on" : ""} onClick={() => go(k)}>
            {label}
          </button>
        ))}
      </div>
      <Tab />
    </div>
  );
}
