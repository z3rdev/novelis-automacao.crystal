import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type DialogName = "updates" | "notifications" | "workflow-completion";
interface DialogState {
  active: DialogName | null;
  show(name: DialogName): void;
  hide(name: DialogName): void;
}
const DialogContext = createContext<DialogState | null>(null);

export function AppDialogs({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<DialogName | null>(null);
  const show = useCallback((name: DialogName) => setActive((previous) => previous ?? name), []);
  const hide = useCallback(
    (name: DialogName) => setActive((previous) => (previous === name ? null : previous)),
    [],
  );
  return <DialogContext.Provider value={{ active, show, hide }}>{children}</DialogContext.Provider>;
}

export function useAppDialogs() {
  const context = useContext(DialogContext);
  if (!context) throw new Error("Os modais precisam de AppDialogs.");
  return context;
}
