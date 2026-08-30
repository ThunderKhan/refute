import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, useLocation } from "react-router-dom";
import App from "./App";
import LiveVerifyPage from "./LiveVerifyPage";
import "./styles.css";
import "./polish.css";
import "./live.css";
import "./github-mode.css";

function RootRoute() {
  const location = useLocation();
  return location.pathname === "/verify" ? <LiveVerifyPage /> : <App />;
}

const root = document.getElementById("root")!;

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <BrowserRouter>
      <RootRoute />
    </BrowserRouter>
  </React.StrictMode>,
);
