import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";
import { desktop } from "@/services/desktop";
import { DeveloperCredit, developerGithubUrl } from "./developer-credit";

vi.mock("@/services/desktop", () => ({ desktop: { openPath: vi.fn() } }));
vi.mock("sonner", () => ({ toast: { error: vi.fn() } }));

beforeEach(() => {
  vi.mocked(desktop.openPath).mockResolvedValue(undefined);
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("crédito do desenvolvedor", () => {
  it("abre o perfil GitHub pelo recurso de navegação do aplicativo", () => {
    render(<DeveloperCredit />);
    expect(screen.getByText("Desenvolvido por")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Z3ro.dev" });
    expect(link).toHaveAttribute("href", "https://github.com/z3rdev");
    fireEvent.click(link);
    expect(desktop.openPath).toHaveBeenCalledExactlyOnceWith(developerGithubUrl);
  });

  it("informa quando a abertura do navegador falha", async () => {
    vi.mocked(desktop.openPath).mockRejectedValueOnce(new Error("fixture"));
    render(<DeveloperCredit />);
    fireEvent.click(screen.getByRole("link", { name: "Z3ro.dev" }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Não foi possível abrir o GitHub."),
    );
  });
});
