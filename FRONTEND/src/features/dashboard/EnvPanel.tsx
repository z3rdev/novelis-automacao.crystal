import { SlidersHorizontal } from "lucide-react";

import type { EnvCatalog } from "../../lib/api";

interface Props {
  catalog: EnvCatalog | null;
}

export function EnvPanel({ catalog }: Props) {
  const groups = Object.entries(catalog?.groups ?? {});

  return (
    <section className="panel env-panel">
      <div className="panel-title">
        <SlidersHorizontal size={18} aria-hidden="true" />
        <h2>Env legado</h2>
        <span className="pill">{catalog?.total ?? 0}</span>
      </div>
      <div className="env-groups">
        {groups.length === 0 ? (
          <p className="muted">Backend offline.</p>
        ) : (
          groups.map(([group, entries]) => (
            <details key={group}>
              <summary>
                <strong>{group}</strong>
                <span>{entries.length}</span>
              </summary>
              <div className="env-list">
                {entries.map((entry) => (
                  <div className="env-row" key={entry.key}>
                    <span>{entry.key}</span>
                    <small>{entry.hasValue ? entry.value || "valor definido" : "vazio"}</small>
                  </div>
                ))}
              </div>
            </details>
          ))
        )}
      </div>
    </section>
  );
}
