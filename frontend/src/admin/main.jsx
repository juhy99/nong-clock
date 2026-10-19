// 관리자 사이트 진입점 (http://localhost:5173/admin/). 사용자 사이트와 화면·메뉴가 완전히 분리되어 있다.
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import AdminApp from "./AdminApp";
import { AuthProvider } from "../components/AuthContext";
import "../styles.css";
import "./admin.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter basename="/admin">
      <AuthProvider>
        <AdminApp />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
