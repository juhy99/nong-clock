import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./components/AuthContext";
import { ErrorPopupProvider } from "./components/ErrorPopup";
import "./styles.css";
import "./theme.css"; // 새 디자인 (v17) — 사용자 사이트만

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ErrorPopupProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ErrorPopupProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
