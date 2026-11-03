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
import News from "./pages/News";
import Search from "./pages/Search";
import BoardList from "./pages/board/BoardList";
import { NoticeView, PostView } from "./pages/board/PostView";
import PostWrite from "./pages/board/PostWrite";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Recommend from "./pages/Recommend";
import { AUCTION_ENABLED } from "./features";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="market" element={<Market />} />
        <Route path="ai" element={<Predict />} />
        <Route path="recommend" element={<Recommend />} />
        {AUCTION_ENABLED ? (
          <>
            <Route path="auctions" element={<Auctions />} />
            <Route path="auctions/:id" element={<AuctionDetail />} />
            <Route path="mypage/auctions/new" element={<RequireAuth><NewAuction /></RequireAuth>} />
          </>
        ) : (
          // 경매 보류 중: 예전 링크로 들어와도 홈으로
          <>
            <Route path="auctions/*" element={<Navigate to="/" replace />} />
            <Route path="mypage/auctions/*" element={<Navigate to="/mypage" replace />} />
          </>
        )}
        <Route path="mypage" element={<RequireAuth><MyPage /></RequireAuth>} />
        <Route path="news" element={<News />} />
        <Route path="search" element={<Search />} />
        <Route path="about" element={<About />} />
        <Route path="board" element={<BoardList />} />
        <Route path="board/write" element={<RequireAuth><PostWrite /></RequireAuth>} />
        <Route path="board/notice/:id" element={<NoticeView />} />
        <Route path="board/:id" element={<PostView />} />
        <Route path="board/:id/edit" element={<RequireAuth><PostWrite /></RequireAuth>} />
        <Route path="login" element={<Login />} />
        <Route path="signup" element={<Signup />} />
        <Route path="*" element={<div className="page"><div className="card state">페이지를 찾을 수 없습니다.</div></div>} />
      </Route>
    </Routes>
  );
}
