import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { appearanceKey, initializeAppearance } from "@/services/appearance";
import { useAppearance } from "@/services/appearance-context";
import { AppearanceProvider } from "./appearance-provider";
import { AppearanceMenu } from "./appearance-menu";

const native = vi.hoisted(() => ({ setTheme: vi.fn().mockResolvedValue(undefined) }));
vi.mock("@/services/desktop", () => ({ desktop: native }));
let dark = false;
const listeners = new Set<(value: MediaQueryListEvent) => void>();
beforeEach(() => {
  dark = false;
  listeners.clear();
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  vi.clearAllMocks();
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({
      matches: dark,
      addEventListener: (_: string, listener: (value: MediaQueryListEvent) => void) =>
        listeners.add(listener),
      removeEventListener: (_: string, listener: (value: MediaQueryListEvent) => void) =>
        listeners.delete(listener),
    })),
  );
  vi.stubGlobal("PointerEvent", MouseEvent);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.documentElement.classList.remove("dark");
});

function Probe() {
  const theme = useAppearance();
  return (
    <>
      <AppearanceMenu />
      <output>
        {theme.preference}/{theme.resolved}
      </output>
    </>
  );
}
function changeSystem(value: boolean) {
  dark = value;
  act(() => listeners.forEach((listener) => listener({ matches: value } as MediaQueryListEvent)));
}

it("salva o tema escolhido, reaplica ao reabrir e mantém a preferência mesmo mudando o sistema", async () => {
  const view = render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Aparência" }));
  await waitFor(() => expect(document.documentElement).toHaveClass("dark"));
  expect(localStorage.getItem(appearanceKey)).toBe("dark");
  expect(screen.queryByRole("menu")).toBeNull();
  changeSystem(false);
  expect(screen.getByText("dark/dark")).toBeInTheDocument();
  view.unmount();
  render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  expect(document.documentElement).toHaveClass("dark");
  expect(native.setTheme).toHaveBeenLastCalledWith("dark");
});

it("alterna a cada clique curto e não abre o menu", () => {
  render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  const button = screen.getByRole("button", { name: "Aparência" });
  fireEvent.click(button);
  expect(screen.getByText("dark/dark")).toBeInTheDocument();
  fireEvent.click(button);
  expect(screen.getByText("light/light")).toBeInTheDocument();
  expect(screen.queryByRole("menu")).toBeNull();
  fireEvent.keyDown(button, { key: "Enter" });
  expect(screen.getByText("dark/dark")).toBeInTheDocument();
});

it("mostra seguir o computador ao segurar, sem alternar o tema ao soltar", () => {
  vi.useFakeTimers();
  localStorage.setItem(appearanceKey, "dark");
  render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  const button = screen.getByRole("button", { name: "Aparência" });
  fireEvent.pointerDown(button, { button: 0, clientX: 10, clientY: 10 });
  act(() => vi.advanceTimersByTime(600));
  const follow = screen.getByRole("menuitemradio", { name: "Seguir o computador" });
  fireEvent.pointerUp(button, { button: 0 });
  fireEvent.click(button);
  expect(screen.getByText("dark/dark")).toBeInTheDocument();
  fireEvent.click(follow);
  expect(screen.getByText("system/light")).toBeInTheDocument();
  expect(localStorage.getItem(appearanceKey)).toBe("system");
  changeSystem(true);
  expect(screen.getByText("system/dark")).toBeInTheDocument();
});

it("cancela o clique longo ao mover ou cancelar e oferece acesso pelo teclado", async () => {
  vi.useFakeTimers();
  render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  const button = screen.getByRole("button", { name: "Aparência" });
  fireEvent.pointerDown(button, { button: 0, clientX: 10, clientY: 10 });
  fireEvent.pointerMove(button, { clientX: 30, clientY: 10 });
  act(() => vi.advanceTimersByTime(700));
  expect(screen.queryByRole("menu")).toBeNull();
  fireEvent.pointerCancel(button);
  fireEvent.click(button);
  expect(screen.getByText("system/light")).toBeInTheDocument();
  fireEvent.keyDown(button, { key: "ArrowDown" });
  expect(screen.getByRole("menuitemradio", { name: "Seguir o computador" })).toBeVisible();
});

it("acompanha o Windows e sincroniza a seleção de outra janela", () => {
  render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  changeSystem(true);
  expect(document.documentElement).toHaveClass("dark");
  act(() =>
    window.dispatchEvent(new StorageEvent("storage", { key: appearanceKey, newValue: "light" })),
  );
  expect(screen.getByText("light/light")).toBeInTheDocument();
  expect(document.documentElement).not.toHaveClass("dark");
  changeSystem(true);
  expect(document.documentElement).not.toHaveClass("dark");
});

it("aplica o tema antes da montagem e funciona com armazenamento indisponível", () => {
  dark = true;
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("unavailable");
  });
  initializeAppearance();
  expect(document.documentElement).toHaveClass("dark");
  render(
    <AppearanceProvider>
      <Probe />
    </AppearanceProvider>,
  );
  expect(screen.getByText("system/dark")).toBeInTheDocument();
});
