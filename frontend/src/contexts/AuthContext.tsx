import { createContext, useContext, useState, useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { api } from "../lib/api";
import { SESSION_EXPIRED_EVENT } from "../lib/auth-events";
import type { UserProfile } from "../lib/contracts";
import { platform } from "../adapters/platform";

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserProfile | null;
  login: (token: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function verifiedProfile(user: UserProfile): UserProfile {
  if (!user?.id || !user.email || !user.full_name || !user.is_active
    || !["ADMIN", "INVESTIGATOR", "ANALYST"].includes(user.role)) {
    throw new Error("Unable to verify an active officer profile.");
  }
  return user;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<UserProfile | null>(null);
  const generation = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const current = generation.current;
    const restore = async () => {
      try {
        const token = await platform.storage.get("crimelens_auth_token");
        if (token) {
          const profile = verifiedProfile(await api.auth.me());
          if (!cancelled && current === generation.current) setUser(profile);
        }
      } catch {
        if (!cancelled && current === generation.current) {
          setUser(null);
          await api.auth.clearToken();
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    const expired = () => {
      generation.current += 1;
      setUser(null);
      setIsLoading(false);
      void api.auth.clearToken().catch(() => { /* In-memory access remains revoked. */ });
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expired);
    void restore();
    return () => {
      cancelled = true;
      window.removeEventListener(SESSION_EXPIRED_EVENT, expired);
    };
  }, []);

  const login = async (token: string) => {
    const current = ++generation.current;
    setUser(null);
    await api.auth.setToken(token);
    try {
      const profile = verifiedProfile(await api.auth.me());
      if (current === generation.current) setUser(profile);
    } catch (error) {
      if (current === generation.current) await api.auth.clearToken();
      throw error;
    }
  };

  const logout = async () => {
    generation.current += 1;
    setUser(null);
    await api.auth.clearToken();
  };

  return <AuthContext.Provider value={{ isAuthenticated: user !== null, isLoading, user, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
