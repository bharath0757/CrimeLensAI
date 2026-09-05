import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../contexts/AuthContext";
import { InterfaceIcon } from "../components/InterfaceIcon";

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
      const response = await api.auth.login(username, password);
      
      const token = response.access_token;
      
      if (!token) {
        throw new Error("Invalid authentication response format");
      }

      await login(token);
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      console.error("Login Error:", err);
      let msg = "Invalid login credentials.";
      if (err.status === 0) {
        msg = typeof err.message === "string" ? err.message : "Unable to connect to authentication service.";
      } else if (err.status === 401 || err.status === 403) {
        msg = "Invalid username or password.";
      } else if (typeof err.message === "string") {
        msg = err.message;
      } else if (err.detail) {
        if (Array.isArray(err.detail)) {
          msg = err.detail[0]?.msg || "Validation error.";
        } else if (typeof err.detail === "string") {
          msg = err.detail;
        }
      }
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="sign-in-page">
      <section className="sign-in-introduction" aria-label="About CrimeLensAI">
        <div className="brand"><span className="brand-mark"><InterfaceIcon name="shield" size={26} /></span><span>CrimeLens<span className="brand-ai">AI</span></span></div>
        <div className="sign-in-story">
          <p className="eyebrow">INVESTIGATION INTELLIGENCE</p>
          <h1>Separate cases.<br /><span>A clearer picture.</span></h1>
          <p className="sign-in-description">Connect evidence across investigations. Follow the relationships that matter, with the source always in view.</p>
          <ol className="sign-in-steps">
            <li><span>01</span><div><strong>Bring evidence together</strong><p>FIRs, entities and case records in one workspace.</p></div></li>
            <li><span>02</span><div><strong>Examine the connections</strong><p>Explore shared identifiers and linked cases.</p></div></li>
            <li><span>03</span><div><strong>Review with accountability</strong><p>Trace the source. Verify the audit trail.</p></div></li>
          </ol>
        </div>
        <p className="sign-in-footnote">Built to support officer judgment, not replace it.</p>
      </section>
      <section className="sign-in-access">
      <div className="sign-in-card">
        <div className="mb-8">
          <span className="sign-in-symbol"><InterfaceIcon name="shield" size={24} /></span>
          <p className="eyebrow">OFFICER ACCESS</p>
          <h2>Welcome back</h2>
          <p className="text-sm text-surface-600 mt-2">Sign in to your investigator account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div role="alert" className="bg-danger-50 text-danger-700 border border-danger-200 p-3 rounded-lg text-sm font-medium">
              {typeof error === 'string' ? error : ((error as any)?.detail?.[0]?.msg || (error as any)?.detail || 'Invalid login credentials')}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-sm font-medium text-surface-600 dark:text-surface-200 transition-colors" htmlFor="username">
              Username
            </label>
            <input
              id="username"
              autoComplete="username"
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
              autoComplete="current-password"
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
        <p className="access-notice"><InterfaceIcon name="shield" size={16} /><span>For authorized personnel. Handle case information according to your department’s policies.</span></p>
      </div>
      <p className="access-help">Need access? Contact your system administrator.</p>
      </section>
    </div>
  );
}
