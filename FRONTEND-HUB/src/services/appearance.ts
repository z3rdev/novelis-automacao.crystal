export type Appearance = "system" | "light" | "dark";
export type ResolvedAppearance = "light" | "dark";
export const appearanceKey = "cargo-hub.appearance";

export function appearanceValue(value: unknown): Appearance {
  return value === "light" || value === "dark" ? value : "system";
}

export function readAppearance(): Appearance {
  try {
    return appearanceValue(localStorage.getItem(appearanceKey));
  } catch {
    return "system";
  }
}

export function resolveAppearance(value: Appearance, systemDark: boolean): ResolvedAppearance {
  return value === "system" ? (systemDark ? "dark" : "light") : value;
}

export function applyAppearance(value: ResolvedAppearance) {
  document.documentElement.classList.toggle("dark", value === "dark");
  document.documentElement.style.colorScheme = value;
}

export function initializeAppearance() {
  applyAppearance(
    resolveAppearance(readAppearance(), window.matchMedia("(prefers-color-scheme: dark)").matches),
  );
}

// Runs before stylesheet loading in the browser shell, matching the desktop entry.
export const appearanceBootScript = `try{var t=localStorage.getItem('${appearanceKey}');var d=t==='dark'||(t!=='light'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);document.documentElement.style.colorScheme=d?'dark':'light'}catch{document.documentElement.classList.toggle('dark',matchMedia('(prefers-color-scheme: dark)').matches)}`;
