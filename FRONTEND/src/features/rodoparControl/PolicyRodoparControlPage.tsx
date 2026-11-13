import { Crosshair } from "lucide-react";
import type { ComponentProps } from "react";

import { useRodoparEnabled } from "../steps/useRodoparEnabled";
import { RodoparControlPage as LegacyRodoparControlPage } from "./RodoparControlPage";

export function RodoparControlPage(props: ComponentProps<typeof LegacyRodoparControlPage>) {
  const enabled = useRodoparEnabled();
  if (enabled) return <LegacyRodoparControlPage {...props} />;
  return (
    <section className="panel rodopar-control-page">
      <div className="panel-title"><Crosshair size={18} aria-hidden="true" /><h2>Controle Rodopar</h2></div>
      <p>Rodopar desabilitado. O PDF utiliza o banco de dados e o Crystal Reports.</p>
      <p className="muted">Os mapas, funções e controles antigos foram preservados.</p>
      <button className="secondary-button" disabled type="button">Controles Rodopar desabilitados</button>
    </section>
  );
}
