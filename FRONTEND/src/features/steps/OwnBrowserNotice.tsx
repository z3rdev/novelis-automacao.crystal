import { Monitor } from "lucide-react";

export function OwnBrowserNotice() {
  return (
    <div
      style={{
        alignItems: "center",
        background: "rgba(15, 23, 42, 0.42)",
        display: "flex",
        inset: 0,
        justifyContent: "center",
        pointerEvents: "none",
        position: "absolute",
        zIndex: 30,
      }}
    >
      <div
        role="status"
        style={{
          alignItems: "center",
          background: "#ffffff",
          border: "1px solid #f3c776",
          borderRadius: 8,
          boxShadow: "0 18px 48px rgba(15, 23, 42, 0.28)",
          color: "#1f2937",
          display: "grid",
          gap: 8,
          justifyItems: "center",
          maxWidth: 360,
          padding: "18px 20px",
          textAlign: "center",
        }}
      >
        <Monitor size={28} color="#92400e" aria-hidden="true" />
        <strong>Executando em navegador próprio</strong>
        <span style={{ color: "#475569", fontSize: 13 }}>
          Continue pela janela do Chromium aberta pela Automação.
        </span>
      </div>
    </div>
  );
}
