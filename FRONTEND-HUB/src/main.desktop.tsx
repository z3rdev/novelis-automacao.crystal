import { createRoot } from "react-dom/client";
import { createHashHistory, RouterProvider } from "@tanstack/react-router";
import { getRouter } from "./router";
import "./styles.css";
import { desktop } from "./services/desktop";

if (desktop.isDesktop) {
  document.documentElement.dataset["native"] = "true";
  document.addEventListener("contextmenu", (event) => event.preventDefault());
}
const router = getRouter(createHashHistory());
createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
