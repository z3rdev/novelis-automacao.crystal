import { createRoot } from "react-dom/client";
import { createHashHistory, RouterProvider } from "@tanstack/react-router";
import { getRouter } from "./router";
import "./styles.css";

const router = getRouter(createHashHistory());
createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
