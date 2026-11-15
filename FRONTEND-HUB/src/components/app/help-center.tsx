import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FluentIcon } from "./fluent-icon";
import { helpTopic, helpTopics } from "./help-content";
import documentsScreenshot from "@/assets/help/cte-documents.png";
import "./help-center.css";

const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");

export function HelpCenter({
  topic = "consulta",
  onTopicChange,
}: {
  topic?: string;
  onTopicChange?(id: string): void;
}) {
  const [selection, setSelection] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const term = normalize(search.trim());
  const matches = useMemo(
    () =>
      helpTopics.filter((item) =>
        normalize(
          [
            item.title,
            item.intro,
            ...(item.steps ?? []),
            ...(item.paragraphs ?? []),
            item.note,
          ].join(" "),
        ).includes(term),
      ),
    [term],
  );
  const requested = helpTopic(onTopicChange ? topic : (selection ?? topic));
  const current = matches.find((item) => item.id === requested.id) ?? matches[0];
  const select = (id: string) => {
    setSelection(id);
    onTopicChange?.(id);
  };
  return (
    <section className="help-center" aria-label="Ajuda">
      <div className="help-toolbar">
        <div className="help-search">
          <FluentIcon name="search" />
          <Input
            aria-label="Buscar na ajuda"
            placeholder="Buscar uma dúvida…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {search && (
            <button aria-label="Limpar busca da ajuda" onClick={() => setSearch("")}>
              <FluentIcon name="cancel" />
            </button>
          )}
        </div>
      </div>
      <div className="help-surface">
        <nav aria-label="Assuntos da ajuda" className="help-topics">
          {matches.map((item) => (
            <button
              key={item.id}
              aria-current={current?.id === item.id ? "page" : undefined}
              onClick={() => select(item.id)}
            >
              <FluentIcon name={item.icon} />
              <span>{item.title}</span>
            </button>
          ))}
          {!matches.length && <p className="help-no-topics">Nenhum assunto encontrado.</p>}
        </nav>
        {current ? (
          <article className="help-article" key={current.id}>
            <h2>{current.title}</h2>
            <p className="help-intro">{current.intro}</p>
            {current.steps && (
              <ol className="help-steps">
                {current.steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            )}
            {current.paragraphs?.map((text) => (
              <p key={text}>{text}</p>
            ))}
            {current.id === "documentos" && (
              <figure className="help-screenshot">
                <div className="help-screenshot-crop">
                  <img
                    src={documentsScreenshot}
                    alt="Tela real do Cargo Hub com PDF e XML disponíveis, Guia/Comprovante como Não exige e Chamado como Pronto."
                  />
                  <span aria-hidden="true" className="help-screenshot-focus" />
                </div>
                <figcaption>
                  Na fila, confira os documentos e o indicador da coluna Chamado.
                </figcaption>
              </figure>
            )}
            {current.note && <aside className="help-note">{current.note}</aside>}
            {current.link && (
              <div className="help-action">
                <Button variant="outline" asChild>
                  <Link to={current.link}>
                    {current.action}
                    <FluentIcon name="forward" />
                  </Link>
                </Button>
              </div>
            )}
          </article>
        ) : (
          <div role="status" className="help-empty">
            <FluentIcon name="search" />
            <h2>Nenhum resultado para “{search}”</h2>
            <p>Tente buscar por CT-e, documento, chamado ou agendamento.</p>
            <Button variant="outline" onClick={() => setSearch("")}>
              Limpar busca
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
