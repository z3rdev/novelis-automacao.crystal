import { Save } from "lucide-react";
import { useEffect, useState } from "react";

import type { StepAction, StepDefinition } from "../../lib/api";

interface Props {
  step: StepDefinition | null;
  onSave: (number: number, patch: Partial<StepDefinition>) => Promise<void>;
}

export function StepEditor({ step, onSave }: Props) {
  const [draft, setDraft] = useState<StepDefinition | null>(step);

  useEffect(() => {
    setDraft(step);
  }, [step]);

  if (!draft) {
    return (
      <section className="panel editor-panel">
        <h2>Editor</h2>
        <p className="muted">Selecione um passo.</p>
      </section>
    );
  }

  async function save() {
    if (!draft) return;
    await onSave(draft.number, {
      label: draft.label,
      action: draft.action,
      x: draft.x,
      y: draft.y,
      input_key: draft.input_key,
      enabled: draft.enabled,
      delay_ms: draft.delay_ms,
    });
  }

  return (
    <section className="panel editor-panel">
      <div className="panel-title">
        <h2>Editor</h2>
        <span className="pill">#{draft.number}</span>
      </div>

      <div className="editor-grid">
        <label className="field wide">
          <span>Rótulo</span>
          <input
            value={draft.label}
            onChange={(event) => setDraft({ ...draft, label: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Ação</span>
          <select
            value={draft.action}
            onChange={(event) =>
              setDraft({ ...draft, action: event.target.value as StepAction })
            }
          >
            <option value="click">click</option>
            <option value="fill">fill</option>
            <option value="wait">wait</option>
            <option value="screenshot">screenshot</option>
          </select>
        </label>
        <label className="field">
          <span>X</span>
          <input
            type="number"
            value={draft.x}
            onChange={(event) => setDraft({ ...draft, x: Number(event.target.value) })}
          />
        </label>
        <label className="field">
          <span>Y</span>
          <input
            type="number"
            value={draft.y}
            onChange={(event) => setDraft({ ...draft, y: Number(event.target.value) })}
          />
        </label>
        <label className="field">
          <span>Input key</span>
          <input
            value={draft.input_key ?? ""}
            onChange={(event) => setDraft({ ...draft, input_key: event.target.value })}
          />
        </label>
        <label className="field">
          <span>Delay ms</span>
          <input
            type="number"
            value={draft.delay_ms ?? ""}
            onChange={(event) =>
              setDraft({
                ...draft,
                delay_ms: event.target.value ? Number(event.target.value) : null,
              })
            }
          />
        </label>
        <label className="field checkbox-field">
          <input
            type="checkbox"
            checked={draft.enabled}
            onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
          />
          <span>Ativo</span>
        </label>
      </div>

      <button className="primary-button" onClick={save} type="button">
        <Save size={16} aria-hidden="true" />
        Salvar passo
      </button>
    </section>
  );
}
