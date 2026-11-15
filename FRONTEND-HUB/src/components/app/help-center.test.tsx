import { useState, type ComponentProps } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { HelpCenter } from "./help-center";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }: ComponentProps<"a"> & { to: string }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));
afterEach(cleanup);

function Help() {
  const [topic, setTopic] = useState("consulta");
  return <HelpCenter topic={topic} onTopicChange={setTopic} />;
}

it("busca uma dúvida sem acentos e permite trocar de assunto sem executar a operação", () => {
  render(<Help />);
  fireEvent.change(screen.getByRole("textbox", { name: "Buscar na ajuda" }), {
    target: { value: "conexao" },
  });
  expect(
    screen.getByRole("heading", { name: "O app perdeu a conexão. O que faço?" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Limpar busca da ajuda" }));
  fireEvent.click(screen.getByRole("button", { name: "Como criar um agendamento" }));
  expect(screen.getByRole("heading", { name: "Como criar um agendamento" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Abrir agendamentos" })).toHaveAttribute(
    "href",
    "/agendamentos",
  );
  expect(
    screen.queryByText(/Entendi este passo|min de leitura|Seu progresso/),
  ).not.toBeInTheDocument();
});

it("abre o assunto indicado pela tela de origem e apresenta a captura real dos documentos", () => {
  const { rerender } = render(<HelpCenter topic="documentos" onTopicChange={vi.fn()} />);
  expect(
    screen.getByRole("heading", { name: "Por que meu CT-e não está pronto?" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("img", { name: /Tela real do Cargo Hub/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Por que meu CT-e não está pronto?" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  rerender(<HelpCenter topic="fluxos" onTopicChange={vi.fn()} />);
  expect(
    screen.getByRole("heading", { name: "Como acompanhar meu fluxo personalizado" }),
  ).toBeInTheDocument();
});

it("trata a busca sem resultados e restaura os assuntos ao limpar", () => {
  render(<Help />);
  fireEvent.change(screen.getByRole("textbox", { name: "Buscar na ajuda" }), {
    target: { value: "termo-inexistente" },
  });
  expect(screen.getByRole("status")).toHaveTextContent("Nenhum resultado");
  expect(screen.queryByRole("article")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Limpar busca" }));
  expect(screen.getByRole("article")).toBeInTheDocument();
});
