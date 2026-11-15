import { fireEvent, screen } from "@testing-library/react";

export async function selectOption(label: string, option: string | RegExp) {
  fireEvent.keyDown(screen.getByRole("combobox", { name: label }), {
    key: "ArrowDown",
  });
  fireEvent.click(await screen.findByRole("option", { name: option }));
}
