/**
 * CrimeLensAI — Frontend Entry Point
 *
 * React 18 application for the Criminal Network Analysis System.
 * Three core screens: Case Intake, Investigator Dashboard, Audit Trail.
 */

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
