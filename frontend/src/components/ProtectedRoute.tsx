import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return <div role="status" className="flex min-h-screen items-center justify-center bg-surface-50 text-surface-900 dark:bg-surface-950 dark:text-white">Verifying your session…</div>;
  }
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}
