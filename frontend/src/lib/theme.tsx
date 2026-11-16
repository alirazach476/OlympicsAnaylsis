import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Theme = "dark" | "light";
const Ctx = createContext<{ theme: Theme; toggle: () => void }>({ theme: "dark", toggle: () => undefined });

function stored(): Theme {
  try {
    return (localStorage.getItem("theme") as Theme) || "dark";
  } catch {
    return "dark";
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(stored);
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  return <Ctx.Provider value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);

/** Chart colours that stay legible in both themes */
export function useChartColors() {
  const { theme } = useTheme();
  return theme === "dark"
    ? { grid: "#28344c", axis: "#94a3b8", tooltipBg: "#111827", tooltipBorder: "#28344c", text: "#eef2f8" }
    : { grid: "#d6ddE9", axis: "#58647a", tooltipBg: "#ffffff", tooltipBorder: "#d6ddE9", text: "#0f172a" };
}
