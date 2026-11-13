import { Check, ExternalLink, Globe, RefreshCw, X } from "lucide-react";
import { useRodoparEnabled } from "./useRodoparEnabled";

interface Props {
  automationRunning: boolean;
  visible: boolean;
  onClose: () => void;
  onOpenDellmar: () => void;
  onOpenHtml5: () => void;
  onOpenRodopar: () => void;
  onRefresh: () => void;
  onAcceptBlueScreen: () => void;
}

export function BrowserPreviewToolbar({
  automationRunning,
  visible,
  onClose,
  onOpenDellmar,
  onOpenHtml5,
  onOpenRodopar,
  onRefresh,
  onAcceptBlueScreen,
}: Props) {
  const rodoparEnabled = useRodoparEnabled();
  return (
    <div className="button-row">
      <button className="secondary-button" disabled={!rodoparEnabled || automationRunning} onClick={onOpenRodopar} type="button">
        <Globe size={16} aria-hidden="true" />
        Rodopar
      </button>
      <button className="secondary-button" disabled={!rodoparEnabled || automationRunning} onClick={onOpenHtml5} type="button">
        <ExternalLink size={16} aria-hidden="true" />
        HTML5
      </button>
      <button className="secondary-button" disabled={!rodoparEnabled || !visible} onClick={onAcceptBlueScreen} type="button">
        <Check size={16} aria-hidden="true" />
        OK tela azul
      </button>
      <button className="secondary-button" disabled={!rodoparEnabled || !visible} onClick={onOpenDellmar} type="button">
        <Check size={16} aria-hidden="true" />
        Abrir Dellmar
      </button>
      <button className="icon-button" disabled={!visible} onClick={onRefresh} title="Atualizar" type="button">
        <RefreshCw size={16} aria-hidden="true" />
      </button>
      <button className="icon-button" onClick={onClose} title="Fechar preview" type="button">
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
