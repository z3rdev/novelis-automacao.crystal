import { FolderPlus, Save, Trash2, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type {
  MapFunctionAction,
  RodoparFunctionGroup,
  RodoparMapFunction,
  RodoparMapPoint,
} from "../../lib/api";
import type { PreviewCapturePoint } from "./mappingTypes";
import { sameMapScope, toMapId } from "./mappingUtils";
import "./mapping.css";

interface Props {
  capturedPoint: PreviewCapturePoint | null;
  groups: RodoparFunctionGroup[];
  functions: RodoparMapFunction[];
  points: RodoparMapPoint[];
  selectedPoint: RodoparMapPoint | null;
  selectedSubTab: string;
  selectedTab: string;
  onDeleteFunction: (item: RodoparMapFunction) => Promise<void>;
  onDeleteGroup: (group: RodoparFunctionGroup) => Promise<void>;
  onSaveFunction: (item: RodoparMapFunction) => Promise<void>;
  onSaveGroup: (group: RodoparFunctionGroup) => Promise<void>;
}

export function MappingFunctionsPanel({
  capturedPoint,
  groups,
  functions,
  points,
  selectedPoint,
  selectedSubTab,
  selectedTab,
  onDeleteFunction,
  onDeleteGroup,
  onSaveFunction,
  onSaveGroup,
}: Props) {
  const [groupName, setGroupName] = useState("");
  const [functionName, setFunctionName] = useState("");
  const [functionId, setFunctionId] = useState("");
  const [action, setAction] = useState<MapFunctionAction>("click");
  const [groupId, setGroupId] = useState("");
  const [pointId, setPointId] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const tabGroups = useMemo(
    () => groups.filter((group) => sameMapScope(group.tab, group.sub_tab, selectedTab, selectedSubTab)),
    [groups, selectedSubTab, selectedTab],
  );
  const tabFunctions = useMemo(
    () => functions.filter((item) => sameMapScope(item.tab, item.sub_tab, selectedTab, selectedSubTab)),
    [functions, selectedSubTab, selectedTab],
  );
  const tabPoints = useMemo(
    () => points.filter((point) => sameMapScope(point.tab, point.sub_tab, selectedTab, selectedSubTab)),
    [points, selectedSubTab, selectedTab],
  );

  useEffect(() => {
    if (groupId && !tabGroups.some((group) => group.id === groupId)) {
      setGroupId("");
    }
  }, [groupId, tabGroups]);

  async function handleSaveGroup() {
    const name = groupName.trim();
    if (!name) {
      setError("Informe o nome do grupo.");
      return;
    }
    const group: RodoparFunctionGroup = {
      id: [toMapId(selectedTab), toMapId(selectedSubTab), toMapId(name)]
        .filter(Boolean)
        .join("."),
      name,
      tab: selectedTab,
      sub_tab: selectedSubTab,
      description: "",
      order: tabGroups.length + 1,
    };
    setBusy(true);
    setError("");
    try {
      await onSaveGroup(group);
      setGroupName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar grupo.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveFunction() {
    const name = functionName.trim();
    const id = (functionId.trim() || toMapId(name)).trim();
    const targetPoint = tabPoints.find((point) => point.id === pointId) ?? selectedPoint;
    const basePoint = capturedPoint ?? targetPoint;
    if (!name || !id) {
      setError("Informe nome e ID da função.");
      return;
    }
    if (!basePoint && action !== "wait") {
      setError("Capture um clique ou selecione um ponto da aba.");
      return;
    }
    const item: RodoparMapFunction = {
      id,
      name,
      tab: selectedTab,
      sub_tab: selectedSubTab,
      group_id: groupId,
      action,
      point_id: capturedPoint ? "" : targetPoint?.id ?? "",
      x: basePoint?.x ?? 0,
      y: basePoint?.y ?? 0,
      viewport: basePoint?.viewport ?? { width: 1024, height: 750, dpr: 1 },
      description: description.trim(),
    };
    setBusy(true);
    setError("");
    try {
      await onSaveFunction(item);
      setFunctionId("");
      setFunctionName("");
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar função.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel mapper-panel">
      <div className="panel-title">
        <Zap size={18} aria-hidden="true" />
        <h2>Funções e grupos</h2>
        <span className="pill">{tabPoints.length} pts</span>
      </div>

      <div className="mapper-status">
        <span>Aba ativa</span>
        <strong>{selectedSubTab ? `${selectedTab} / ${selectedSubTab}` : selectedTab}</strong>
      </div>

      <div className="mapper-inline-form">
        <label className="field">
          <span>Novo grupo</span>
          <input
            placeholder="ex: Consulta CTRC"
            value={groupName}
            onChange={(event) => setGroupName(event.target.value)}
          />
        </label>
        <button className="icon-button" disabled={busy} onClick={handleSaveGroup} type="button">
          <FolderPlus size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="mapper-grid">
        <label className="field">
          <span>Grupo</span>
          <select value={groupId} onChange={(event) => setGroupId(event.target.value)}>
            <option value="">Sem grupo</option>
            {tabGroups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Ação</span>
          <select value={action} onChange={(event) => setAction(event.target.value as MapFunctionAction)}>
            <option value="click">Clique</option>
            <option value="fill">Preencher</option>
            <option value="wait">Aguardar</option>
            <option value="other">Outra</option>
          </select>
        </label>
        <label className="field">
          <span>ID função</span>
          <input
            placeholder="ex: abrir_geral"
            value={functionId}
            onChange={(event) => setFunctionId(event.target.value)}
          />
        </label>
        <label className="field">
          <span>Nome</span>
          <input
            placeholder="ex: Abrir aba Geral"
            value={functionName}
            onChange={(event) => setFunctionName(event.target.value)}
          />
        </label>
        <label className="field wide">
          <span>Ponto vinculado ({tabPoints.length})</span>
          <select value={pointId} onChange={(event) => setPointId(event.target.value)}>
            <option value="">Capturado ou selecionado</option>
            {tabPoints.map((point) => (
              <option key={point.id} value={point.id}>
                {point.id}
              </option>
            ))}
          </select>
        </label>
        <div className="field wide">
          <span>Pontos disponíveis</span>
          <div className="linked-point-list">
            {tabPoints.length ? (
              tabPoints.map((point) => (
                <button
                  className={pointId === point.id ? "linked-point-row selected" : "linked-point-row"}
                  key={`${point.tab}:${point.sub_tab ?? ""}:${point.id}`}
                  onClick={() => setPointId(point.id)}
                  type="button"
                >
                  <strong>{point.id}</strong>
                  <span>
                    {point.kind} - {point.x},{point.y}
                  </span>
                </button>
              ))
            ) : (
              <p className="muted compact">Nenhum ponto cadastrado nesta aba.</p>
            )}
          </div>
        </div>
        <label className="field wide">
          <span>Descrição</span>
          <input
            placeholder="opcional"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
      </div>

      {error ? <p className="error-text">{error}</p> : null}

      <div className="button-row">
        <button className="primary-button" disabled={busy} onClick={handleSaveFunction} type="button">
          <Save size={16} aria-hidden="true" />
          Salvar função
        </button>
      </div>

      <div className="function-group-list">
        {!tabGroups.length && !tabFunctions.length ? (
          <p className="muted compact">Nenhum grupo ou função neste escopo.</p>
        ) : null}
        {tabGroups.map((group) => (
          <details key={group.id} open>
            <summary>
              <strong>{group.name}</strong>
              <button className="icon-button small" onClick={() => onDeleteGroup(group)} type="button">
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </summary>
            {tabFunctions
              .filter((item) => item.group_id === group.id)
              .map((item) => (
                <FunctionRow item={item} key={item.id} onDelete={onDeleteFunction} />
              ))}
          </details>
        ))}
        {tabFunctions
          .filter((item) => !item.group_id)
          .map((item) => (
            <FunctionRow item={item} key={item.id} onDelete={onDeleteFunction} />
          ))}
      </div>
    </section>
  );
}

function FunctionRow({
  item,
  onDelete,
}: {
  item: RodoparMapFunction;
  onDelete: (item: RodoparMapFunction) => Promise<void>;
}) {
  return (
    <div className="function-row">
      <span>{item.name}</span>
      <small>
        {item.action} - {item.x},{item.y}
      </small>
      <button className="icon-button small" onClick={() => onDelete(item)} type="button">
        <Trash2 size={14} aria-hidden="true" />
      </button>
    </div>
  );
}
