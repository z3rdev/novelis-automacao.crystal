import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { AppDatePicker } from "./app-date-picker";

afterEach(cleanup);

it("seleciona pelo calendário do app, respeita os limites e devolve a data local em ISO", async () => {
  function Field() {
    const [value, setValue] = useState("2026-11-14");
    return (
      <>
        <AppDatePicker
          label="Data da consulta"
          value={value}
          onChange={setValue}
          min="2026-11-10"
          max="2026-11-15"
        />
        <output>{value}</output>
      </>
    );
  }
  const { container } = render(<Field />);
  fireEvent.click(screen.getByRole("button", { name: "Data da consulta" }));
  expect(await screen.findByRole("button", { name: /, 9 de novembro de 2026/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: /16 de novembro de 2026/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /15 de novembro de 2026/ }));
  expect(screen.getByText("2026-11-15")).toBeVisible();
  expect(screen.getByRole("button", { name: "Data da consulta" })).toHaveTextContent("15/11/2026");
  expect(container.querySelector('input[type="date"]')).toBeNull();
});

it("mantém a escolha bloqueada enquanto a consulta estiver em execução", () => {
  render(
    <AppDatePicker
      label="Data da consulta"
      value="2026-11-15"
      onChange={() => {
        throw new Error("disabled picker changed");
      }}
      disabled
    />,
  );
  expect(screen.getByRole("button", { name: "Data da consulta" })).toBeDisabled();
});
