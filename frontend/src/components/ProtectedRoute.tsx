import { Outlet } from "react-router-dom";
// import { Navigate } from "react-router-dom";
// import { useAuth } from "../contexts/AuthContext";

export function ProtectedRoute() {
  // const { isAuthenticated, isLoading } = useAuth();

  // TEMPORARY BYPASS: Disable route protection for frontend-only development
  /*
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-surface-950 text-white">
        <div className="flex flex-col items-center">
          <p className="text-4xl mb-4 animate-spin">🕸️</p>
          <h2 className="text-xl font-medium">Loading CrimeLensAI...</h2>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  */

  return <Outlet />;
}
