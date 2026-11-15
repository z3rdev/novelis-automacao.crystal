import { createRoot } from "react-dom/client";
import "./styles.css";
import { desktop } from "./services/desktop";
import { installNativeShortcuts } from "./services/native-shortcuts";
import { initializeAppearance } from "./services/appearance";

initializeAppearance();

if (desktop.isDesktop) {
  document.documentElement.dataset["native"] = "true";
  document.addEventListener("contextmenu", (event) => event.preventDefault());
  installNativeShortcuts(document);
}
async function renderWindow() {
  const root = createRoot(document.getElementById("root")!);
  if (
    new URLSearchParams(window.location.search).get("widget") === "1" ||
    (await desktop.isWidgetWindow())
  ) {
    const { StatusWidget } = await import("./components/app/widget/status-widget");
    root.render(<StatusWidget />);
    return;
  }
  const [{ createHashHistory, RouterProvider }, { getRouter }] = await Promise.all([
    import("@tanstack/react-router"),
    import("./router"),
  ]);
  const router = getRouter(createHashHistory());
  root.render(<RouterProvider router={router} />);
}
void renderWindow();
