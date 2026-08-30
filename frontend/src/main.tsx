import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import LiveVerifyPage from "./LiveVerifyPage";
import "./styles.css";
import "./polish.css";
import "./live.css";
import "./github-mode.css";

const root = document.getElementById("root")!;
const isLiveVerifyRoute = window.location.pathname === "/verify";

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <BrowserRouter>
      {isLiveVerifyRoute ? <LiveVerifyPage /> : <App />}
    </BrowserRouter>
  </React.StrictMode>,
);
