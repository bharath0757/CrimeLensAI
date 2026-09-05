import { createContext, useContext, useLayoutEffect } from "react";
import type { ReactNode } from "react";

// The union keeps existing graph renderers compatible with this light-only UI.
type Theme = "light" | "dark";
const lightTheme: { theme: Theme } = { theme: "light" };
const ThemeContext = createContext(lightTheme);

export function ThemeProvider({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    document.documentElement.classList.remove("dark");
    document.documentElement.style.colorScheme = "light";
    try {
      localStorage.removeItem("crimelens-theme");
    } catch {
      // Storage can be disabled; the visual theme does not depend on storage.
    }
  }, []);

  return <ThemeContext.Provider value={lightTheme}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
