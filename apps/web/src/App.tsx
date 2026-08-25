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
import { AuditTrail } from "./pages/AuditTrail";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/cases/new" element={<CaseIntake />} />
          <Route path="/audit" element={<AuditTrail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
