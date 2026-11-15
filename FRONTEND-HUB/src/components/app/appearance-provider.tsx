import { useEffect, useState, type ReactNode } from "react";
import {
  appearanceKey,
  appearanceValue,
  applyAppearance,
  readAppearance,
  resolveAppearance,
  type Appearance,
} from "@/services/appearance";
import { AppearanceContext } from "@/services/appearance-context";
import { desktop } from "@/services/desktop";

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<Appearance>(() =>
    typeof window === "undefined" ? "system" : readAppearance(),
  );
  const [systemDark, setSystemDark] = useState(
    () =>
      typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches,
  );
  const resolved = resolveAppearance(preference, systemDark);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const change = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    const storage = (event: StorageEvent) => {
      if (event.key === appearanceKey || event.key === null)
        setPreference(appearanceValue(event.newValue));
    };
    media.addEventListener("change", change);
    window.addEventListener("storage", storage);
    return () => {
      media.removeEventListener("change", change);
      window.removeEventListener("storage", storage);
    };
  }, []);
  useEffect(() => {
    applyAppearance(resolved);
    // Older preview executables may not carry the new window permission yet.
    void desktop.setTheme(preference === "system" ? null : resolved).catch(() => {});
  }, [resolved, preference]);
  function choose(value: Appearance) {
    try {
      localStorage.setItem(appearanceKey, value);
    } catch {
      /* Remains usable for this session. */
    }
    setPreference(value);
  }
  return (
    <AppearanceContext.Provider value={{ preference, resolved, setPreference: choose }}>
      {children}
    </AppearanceContext.Provider>
  );
}
