interface Props {
  confirming: boolean;
  error: string;
  onConfirm: () => void;
  runId?: string;
}

export function RodoparLoginGate({ confirming, error, onConfirm, runId }: Props) {
  return (
    <div
      aria-labelledby="rodopar-login-modal-title"
      aria-modal="true"
      className="preview-login-modal"
      role="dialog"
    >
      <strong id="rodopar-login-modal-title">HTML5 detectado. Automação pausada.</strong>
      <span>Clique no OK da tela azul e faça login. Depois confirme aqui para continuar os passos.</span>
      {error ? <small className="preview-login-modal-error">{error}</small> : null}
      <button
        className="primary-button"
        disabled={confirming || !runId}
        onClick={onConfirm}
        type="button"
      >
        {confirming ? "Confirmando..." : "Continuar automação"}
      </button>
    </div>
  );
}
