import { describe, expect, it } from "vitest";
import { installNativeShortcuts } from "./native-shortcuts";

describe("Atalhos da janela nativa", () => {
  it("bloqueia F12 e Ctrl+Shift+I inclusive quando só o código físico da tecla está disponível", () => {
    const remove = installNativeShortcuts(document);
    for (const keys of [
      { key: "F12", code: "F12" },
      { key: "Unidentified", code: "F12" },
      { key: "I", code: "KeyI", ctrlKey: true, shiftKey: true },
      { key: "Unidentified", code: "KeyI", ctrlKey: true, shiftKey: true },
      { key: "i", code: "KeyI", metaKey: true, shiftKey: true },
    ]) {
      const event = new KeyboardEvent("keydown", { ...keys, bubbles: true, cancelable: true });
      expect(document.dispatchEvent(event)).toBe(false);
      expect(event.defaultPrevented).toBe(true);
    }
    expect(
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "i", ctrlKey: true, cancelable: true }),
      ),
    ).toBe(true);
    remove();
    expect(
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "F12", cancelable: true })),
    ).toBe(true);
  });
  it("bloqueia impressão e impressão do sistema, preservando digitação comum", () => {
    const remove = installNativeShortcuts(document);
    for (const modifiers of [
      { ctrlKey: true },
      { ctrlKey: true, shiftKey: true },
      { metaKey: true },
    ]) {
      const event = new KeyboardEvent("keydown", {
        key: "p",
        code: "KeyP",
        cancelable: true,
        ...modifiers,
      });
      expect(document.dispatchEvent(event)).toBe(false);
      expect(event.defaultPrevented).toBe(true);
    }
    expect(
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "p", cancelable: true })),
    ).toBe(true);
    expect(
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "c", ctrlKey: true, cancelable: true }),
      ),
    ).toBe(true);
    remove();
    expect(
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: "p", ctrlKey: true, cancelable: true }),
      ),
    ).toBe(true);
  });
});
