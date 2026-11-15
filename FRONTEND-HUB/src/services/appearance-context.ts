import { createContext, useContext } from "react";
import type { Appearance, ResolvedAppearance } from "./appearance";

export const AppearanceContext = createContext<{
  preference: Appearance;
  resolved: ResolvedAppearance;
  setPreference(value: Appearance): void;
}>({ preference: "system", resolved: "light", setPreference: () => {} });

export function useAppearance() {
  return useContext(AppearanceContext);
}
