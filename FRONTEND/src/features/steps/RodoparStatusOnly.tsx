import { RodoparLoginGate } from "./RodoparLoginGate";

interface Props {
  automationRunning: boolean;
  confirmed: boolean;
  confirming: boolean;
  error: string;
  onConfirm: () => void;
  runId?: string;
  submitted: boolean;
}

export function RodoparStatusOnly({
  automationRunning,
  confirmed,
  confirming,
  error,
  onConfirm,
  runId,
  submitted,
}: Props) {
  const showGate = automationRunning && !confirmed && !submitted;
  return (
    <div className="rodopar-status-only">
      <div className="rodopar-status-card">
        <strong>Preview do Rodopar desativado.</strong>
        <span>Use somente a janela HTML5/Chrome aberta pela automação.</span>
        {showGate ? (
          <RodoparLoginGate
            confirming={confirming}
            error={error}
            onConfirm={onConfirm}
            runId={runId}
          />
        ) : (
          <span className="muted">Automação Rodopar em navegador próprio.</span>
        )}
      </div>
    </div>
  );
}
