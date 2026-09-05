/**
 * CrimeLensAI — App Component
 *
 * Root application component with routing to all three core screens:
 * 1. Case Intake — live extraction preview
 * 2. Investigator Dashboard — stat cards, case linkage graph, entity actions
 * 3. Audit Trail — ledger verification table, evidence PDF export
 */

import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { ProtectedRoute } from "./components/ProtectedRoute";

const Login = lazy(() => import("./pages/Login").then(module => ({ default: module.Login })));
const Dashboard = lazy(() => import("./pages/Dashboard").then(module => ({ default: module.Dashboard })));
const NetworkAnalysis = lazy(() => import("./pages/NetworkAnalysis").then(module => ({ default: module.NetworkAnalysis })));
const CaseLinkage = lazy(() => import("./pages/CaseLinkage").then(module => ({ default: module.CaseLinkage })));
const CaseIntake = lazy(() => import("./pages/CaseIntake").then(module => ({ default: module.CaseIntake })));
const StructuredEvidence = lazy(() => import("./pages/StructuredEvidence").then(module => ({ default: module.StructuredEvidence })));
const AuditTrail = lazy(() => import("./pages/AuditTrail").then(module => ({ default: module.AuditTrail })));

const routeLoading = (
  <div className="flex min-h-screen items-center justify-center bg-surface-50 text-surface-600 dark:bg-surface-950 dark:text-surface-200" role="status">
    Loading CrimeLensAI…
  </div>
);

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={routeLoading}>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/network" element={<NetworkAnalysis />} />
                  <Route path="/case-linkage" element={<CaseLinkage />} />
                  <Route path="/cases/new" element={<CaseIntake />} />
                  <Route path="/evidence" element={<StructuredEvidence />} />
                  <Route path="/audit" element={<AuditTrail />} />
                </Route>
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
