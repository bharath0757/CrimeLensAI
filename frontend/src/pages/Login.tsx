import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // If user is already authenticated, redirect to dashboard.
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const response: any = await api.auth.login(username, password);
      
      // The API should ideally return an access_token. We adapt based on common JWT formats.
      const token = response.access_token || response.token;
      
      if (!token) {
        throw new Error("Invalid authentication response format");
      }

      await login(token);
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      console.error("Login Error:", err);
      if (err.status === 0) {
        setError(err.message || "Unable to connect to authentication service.");
      } else if (err.status === 401 || err.status === 403) {
        setError("Invalid username or password.");
      } else {
        setError(err.message || "An unexpected error occurred during login.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-surface-50 dark:bg-surface-950 text-surface-900 dark:text-white p-4 transition-colors">
      <div className="w-full max-w-md bg-white dark:bg-surface-900 border border-surface-200 dark:border-surface-800 rounded-2xl p-8 shadow-2xl transition-colors">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold bg-gradient-to-r from-primary-600 to-primary-700 dark:from-primary-400 dark:to-primary-600 bg-clip-text text-transparent transition-colors">
            CrimeLensAI
          </h1>
          <p className="text-sm text-surface-600 dark:text-surface-300 mt-2 transition-colors">Sign in to your investigator account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-danger-50 text-danger-700 border border-danger-200 dark:bg-danger-500/10 dark:border-danger-500/20 dark:text-danger-500 p-3 rounded-lg text-sm font-medium transition-colors">
              ⚠️ {error}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-sm font-medium text-surface-600 dark:text-surface-200 transition-colors" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-surface-50 border border-surface-200 text-surface-900 focus:border-primary-500 dark:bg-surface-950 dark:border-surface-700 rounded-lg px-4 py-2 dark:text-white dark:focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 transition-colors"
              placeholder="Enter your username"
            />
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium text-surface-600 dark:text-surface-200 transition-colors" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-surface-50 border border-surface-200 text-surface-900 focus:border-primary-500 dark:bg-surface-950 dark:border-surface-700 rounded-lg px-4 py-2 dark:text-white dark:focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 transition-colors"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-primary-600 hover:bg-primary-700 dark:hover:bg-primary-500 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-4"
          >
            {isSubmitting ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
