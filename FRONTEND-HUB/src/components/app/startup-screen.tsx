import { useEffect, useState, type ReactNode } from "react";
import { BrandMark, BrandName } from "./brand";

export function StartupScreen({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<"enter" | "exit" | "done">("enter");
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const exit = window.setTimeout(() => setPhase("exit"), reduced ? 0 : 2600);
    const done = window.setTimeout(() => setPhase("done"), reduced ? 0 : 3100);
    return () => {
      window.clearTimeout(exit);
      window.clearTimeout(done);
    };
  }, []);
  useEffect(() => {
    if (phase === "exit") document.getElementById("operator-name")?.focus();
  }, [phase]);

  return (
    <>
      <div className="cargo-app-content" data-ready={phase !== "enter"} inert={phase === "enter"}>
        {children}
      </div>
      {phase !== "done" && (
        <div
          className="cargo-splash"
          data-phase={phase}
          role="status"
          aria-label="Iniciando o Cargo Hub"
        >
          <div className="cargo-splash__background" />
          <div className="cargo-splash__beam" />
          <div className="cargo-splash__identity">
            <div className="cargo-splash__orbit" aria-hidden="true" />
            <div className="cargo-splash__mark">
              <BrandMark />
              <BrandMark tone="white" className="cargo-splash__alternate" />
              <span className="cargo-splash__shine" />
            </div>
            <BrandName className="cargo-splash__name" />
            <p className="cargo-splash__subtitle">Automação Novelis</p>
            <div className="cargo-splash__loading">
              <span />
            </div>
            <p className="cargo-splash__status">Iniciando o Cargo Hub…</p>
          </div>
        </div>
      )}
    </>
  );
}
