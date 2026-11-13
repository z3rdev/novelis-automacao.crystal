import { FileText, Globe } from "lucide-react";
import type { ComponentProps } from "react";

import { API_BASE } from "../../lib/api";
import { BrowserPreview as LegacyBrowserPreview } from "./BrowserPreview";
import { LiveBrowserSnapshot } from "./LiveBrowserSnapshot";
import { useRodoparEnabled } from "./useRodoparEnabled";

type Props = ComponentProps<typeof LegacyBrowserPreview>;
const OLD_FLOWS = ["pre-passo", "integrado", "pdf-rodopar", "rodopar-pdf"];

export function BrowserPreview(props: Props) {
  const enabled = useRodoparEnabled();
  const flow = props.run?.flow || "pendentes";
  if (enabled || (!props.captureEnabled && !["pendentes", "consulta-pendentes", "consulta", ...OLD_FLOWS].includes(flow))) {
    return <LegacyBrowserPreview {...props} />;
  }
  const running = props.run?.status === "running" || props.run?.status === "stopping";
  const generated = props.events?.find((event) => event.run_id === props.run?.id && event.kind === "crystal_pdf.generated");
  const file = String(generated?.payload?.pdfFile || "").split(/[\\/]/).pop();
  return (
    <section className="panel preview-panel">
      <div className="panel-title"><Globe size={18} aria-hidden="true" /><h2>Execução sem Rodopar</h2></div>
      <p className="muted">Acesso ao Rodopar desabilitado. O DACTE é gerado diretamente pelo banco e pelo Crystal.</p>
      {file ? (
        <p><a className="secondary-button" href={`${API_BASE}/reports/dacte/files/${encodeURIComponent(file)}`} target="_blank" rel="noreferrer">
          <FileText size={16} aria-hidden="true" /> Visualizar PDF gerado (teste)
        </a></p>
      ) : null}
      {running && !OLD_FLOWS.includes(flow) && !props.captureEnabled ? (
        <div className="browser-frame-scroll"><div className="browser-frame"><LiveBrowserSnapshot enabled={running} /></div></div>
      ) : <p className="muted">O fluxo e os controles antigos foram preservados e estão desabilitados.</p>}
    </section>
  );
}
