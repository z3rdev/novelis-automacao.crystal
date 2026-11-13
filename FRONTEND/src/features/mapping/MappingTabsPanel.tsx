import { FolderPlus, Layers, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import type { RodoparMapPoint, RodoparMapSubTab } from "../../lib/api";
import { sameMapName, sameMapScope } from "./mappingUtils";
import "./mapping.css";

interface Props {
  tabs: string[];
  subTabs: RodoparMapSubTab[];
  points: RodoparMapPoint[];
  selectedTab: string;
  selectedSubTab: string;
  onCreateTab: (name: string) => Promise<void>;
  onCreateSubTab: (name: string) => Promise<void>;
  onTabChange: (tab: string) => void;
  onSubTabChange: (subTab: string) => void;
}

export function MappingTabsPanel({
  tabs,
  subTabs,
  points,
  selectedTab,
  selectedSubTab,
  onCreateTab,
  onCreateSubTab,
  onTabChange,
  onSubTabChange,
}: Props) {
  const [newTabName, setNewTabName] = useState("");
  const [newSubTabName, setNewSubTabName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const activeSubTabs = useMemo(
    () => subTabs.filter((item) => sameMapName(item.tab, selectedTab)),
    [selectedTab, subTabs],
  );
  const selectedMainPoints = useMemo(
    () => points.filter((point) => sameMapScope(point.tab, point.sub_tab, selectedTab, "")),
    [points, selectedTab],
  );

  async function handleCreateTab() {
    const name = newTabName.trim();
    if (!name) {
      setError("Informe o nome da aba.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onCreateTab(name);
      setNewTabName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar aba.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateSubTab() {
    const name = newSubTabName.trim();
    if (!name) {
      setError("Informe o nome da subaba.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await onCreateSubTab(name);
      setNewSubTabName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao criar subaba.");
    } finally {
      setBusy(false);
    }
  }

  function changeTab(tab: string) {
    onTabChange(tab);
    onSubTabChange("");
  }

  return (
    <section className="panel mapper-panel">
      <div className="panel-title">
        <Layers size={18} aria-hidden="true" />
        <h2>Abas</h2>
        <span className="pill">{tabs.length}</span>
      </div>

      <div className="mapper-inline-form">
        <label className="field">
          <span>Nova aba principal</span>
          <input
            placeholder="ex: Fiscal"
            value={newTabName}
            onChange={(event) => setNewTabName(event.target.value)}
          />
        </label>
        <button className="icon-button" disabled={busy} onClick={handleCreateTab} type="button">
          <Plus size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="mapper-tab-groups">
        {tabs.map((tab) => {
          const count = points.filter((point) => sameMapName(point.tab, tab)).length;
          return (
            <button
              className={sameMapName(selectedTab, tab) ? "mapper-tab active" : "mapper-tab"}
              key={tab}
              onClick={() => changeTab(tab)}
              type="button"
            >
              <span>{tab}</span>
              <small>{count} pts</small>
            </button>
          );
        })}
      </div>

      <div className="mapper-status">
        <span>Aba selecionada</span>
        <strong>{selectedTab}</strong>
      </div>

      <div className="mapper-inline-form">
        <label className="field">
          <span>Nova subaba</span>
          <input
            placeholder="ex: Programacoes"
            value={newSubTabName}
            onChange={(event) => setNewSubTabName(event.target.value)}
          />
        </label>
        <button className="icon-button" disabled={busy} onClick={handleCreateSubTab} type="button">
          <FolderPlus size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="subtab-list">
        <button
          className={!selectedSubTab ? "subtab-row active" : "subtab-row"}
          onClick={() => onSubTabChange("")}
          type="button"
        >
          <strong>Principal</strong>
          <span>{selectedMainPoints.length} ponto(s)</span>
        </button>
        {activeSubTabs.map((item) => (
          <button
            className={sameMapName(selectedSubTab, item.id) ? "subtab-row active" : "subtab-row"}
            key={`${item.tab}:${item.id}`}
            onClick={() => onSubTabChange(item.id)}
            type="button"
          >
            <strong>{item.name}</strong>
            <span>
              {
                points.filter((point) =>
                  sameMapScope(point.tab, point.sub_tab, item.tab, item.id),
                ).length
              }{" "}
              ponto(s)
            </span>
          </button>
        ))}
      </div>

      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}
