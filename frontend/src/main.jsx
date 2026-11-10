import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./components/AuthContext";
import { ErrorPopupProvider } from "./components/ErrorPopup";
import "./styles.css";

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
