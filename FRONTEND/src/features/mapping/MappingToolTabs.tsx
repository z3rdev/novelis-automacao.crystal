export type MappingToolView = "tabs" | "points" | "functions";

interface Props {
  active: MappingToolView;
  onChange: (view: MappingToolView) => void;
}

const TOOLS: Array<{ key: MappingToolView; label: string }> = [
  { key: "tabs", label: "Abas" },
  { key: "points", label: "Pontos" },
  { key: "functions", label: "Funções" },
];

export function MappingToolTabs({ active, onChange }: Props) {
  return (
    <div className="mapping-tool-tabs">
      {TOOLS.map((tool) => (
        <button
          className={active === tool.key ? "active" : ""}
          key={tool.key}
          onClick={() => onChange(tool.key)}
          type="button"
        >
          {tool.label}
        </button>
      ))}
    </div>
  );
}
