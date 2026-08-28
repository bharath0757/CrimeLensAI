import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { api } from "../lib/api";
import { platform } from "../adapters/platform";

interface User {
  username?: string;
  name?: string;
  role?: string;
  [key: string]: any;
}

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  login: (token: string, userData?: User) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const checkSession = async () => {
      try {
        const token = await platform.storage.get("crimelens_auth_token");
        if (token) {
          setIsAuthenticated(true);
          try {
            const userData = await api.auth.me();
            setUser(userData as User);
          } catch {
            setUser({
              id: "dev-user-1",
              email: "investigator@crimelens.ai",
              role: "Investigator",
            });
          }
        }
      } catch (err) {
        console.error("Failed to check session", err);
      } finally {
        setIsLoading(false);
      }
    };
    checkSession();
  }, []);

  const login = async (token: string, userData?: User) => {
    await api.auth.setToken(token);
    setIsAuthenticated(true);
    if (userData) {
      setUser(userData);
    } else {
      try {
        const data = await api.auth.me();
        setUser(data as User);
      } catch {
        setUser({
          id: "dev-user-1",
          email: "investigator@crimelens.ai",
          role: "Investigator",
        });
      }
    }
  };

  const logout = async () => {
    await api.auth.clearToken();
    setIsAuthenticated(false);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
