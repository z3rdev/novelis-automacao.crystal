import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { DeviceCard } from "./device-card";

afterEach(cleanup);
it("destaca o setor e mantém o computador em texto menor sem o bloco de classificação", () => {
  render(
    <DeviceCard
      identity={{
        computer_name: "NB-TI-VIN-07",
        windows_user: "DOMAIN\\operator",
        mac_addresses: [],
      }}
    />,
  );
  expect(screen.getByRole("heading", { name: "Tecnologia da informação" })).toBeVisible();
  expect(screen.getByText("NB-TI-VIN-07")).toHaveClass("text-sm");
  expect(screen.queryByText("Viana")).toBeNull();
  expect(screen.queryByText("Notebook")).toBeNull();
  expect(screen.queryByText("Dispositivo", { exact: true })).toBeNull();
});
it("mantém os campos desconhecidos explícitos sem inventar um setor", () => {
  render(
    <DeviceCard
      identity={{ computer_name: "NB-PINDA02", windows_user: "D\\user", mac_addresses: [] }}
    />,
  );
  expect(screen.getByRole("heading", { name: "Setor não identificado" })).toBeVisible();
  expect(screen.getByText("NB-PINDA02")).toBeVisible();
});
