import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { RequireAuth } from "./components/AuthContext";
import Home from "./pages/Home";
import Market from "./pages/Market";
import Predict from "./pages/Predict";
import Auctions from "./pages/Auctions";
import AuctionDetail from "./pages/AuctionDetail";
import MyPage from "./pages/mypage/MyPage";
import NewAuction from "./pages/mypage/NewAuction";
import About from "./pages/About";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import AdminLayout from "./pages/admin/AdminLayout";
import Reports from "./pages/admin/Reports";
import Notices from "./pages/admin/Notices";
import SystemStatus from "./pages/admin/SystemStatus";
import DataStatus from "./pages/admin/DataStatus";
import ModelPerformance from "./pages/admin/ModelPerformance";
import Members from "./pages/admin/Members";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="market" element={<Market />} />
        <Route path="ai" element={<Predict />} />
        <Route path="auctions" element={<Auctions />} />
        <Route path="auctions/:id" element={<AuctionDetail />} />
        <Route path="mypage" element={<RequireAuth><MyPage /></RequireAuth>} />
        <Route path="mypage/auctions/new" element={<RequireAuth><NewAuction /></RequireAuth>} />
        <Route path="about" element={<About />} />
        <Route path="login" element={<Login />} />
        <Route path="signup" element={<Signup />} />
        <Route path="admin" element={<RequireAuth admin><AdminLayout /></RequireAuth>}>
          <Route index element={<Navigate to="system" replace />} />
          <Route path="system" element={<SystemStatus />} />
          <Route path="data" element={<DataStatus />} />
          <Route path="model" element={<ModelPerformance />} />
          <Route path="reports" element={<Reports />} />
          <Route path="notices" element={<Notices />} />
          <Route path="members" element={<Members />} />
        </Route>
        <Route path="*" element={<div className="page"><div className="card state">페이지를 찾을 수 없습니다.</div></div>} />
      </Route>
    </Routes>
  );
}
