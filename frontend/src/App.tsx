/**
 * CrimeLensAI — App Component
 *
 * Root application component with routing to all three core screens:
 * 1. Case Intake — live extraction preview
 * 2. Investigator Dashboard — stat cards, case linkage graph, entity actions
 * 3. Audit Trail — ledger verification table, evidence PDF export
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { CaseIntake } from "./pages/CaseIntake";
import { Dashboard } from "./pages/Dashboard";
import { NetworkAnalysis } from "./pages/NetworkAnalysis";
import { CaseLinkage } from "./pages/CaseLinkage";
import { AuditTrail } from "./pages/AuditTrail";
import { Login } from "./pages/Login";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { ProtectedRoute } from "./components/ProtectedRoute";

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/network" element={<NetworkAnalysis />} />
                <Route path="/case-linkage" element={<CaseLinkage />} />
                <Route path="/cases/new" element={<CaseIntake />} />
                <Route path="/audit" element={<AuditTrail />} />
              </Route>
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
