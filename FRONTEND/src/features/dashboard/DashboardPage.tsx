import { AlertCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { ChamadosPage } from "../chamados/ChamadosPage";
import { EventLog } from "../events/EventLog";
import { useAutomationEvents } from "../events/useAutomationEvents";
import { DashboardNav, type DashboardView } from "./DashboardNav";
import { EnvPanel } from "./EnvPanel";
import { LiveBrowserPage } from "../liveBrowser/LiveBrowserPage";
import { MappingFunctionsPanel } from "../mapping/MappingFunctionsPanel";
import { MappingTabsPanel } from "../mapping/MappingTabsPanel";
import { MapperPanel } from "../mapping/MapperPanel";
import { MappingToolTabs, type MappingToolView } from "../mapping/MappingToolTabs";
import type { PreviewCapturePoint } from "../mapping/mappingTypes";
import {
  DEFAULT_RODOPAR_TABS,
  emptyMappingCatalog,
  mapPointKey,
  sameMapName,
  sameMapScope,
  toMapId,
} from "../mapping/mappingUtils";
import { RunControls } from "../runner/RunControls";
import { PendentesPlanPage } from "../pendentes/PendentesPlanPage";
import { RodoparControlPage } from "../rodoparControl/PolicyRodoparControlPage";
import { BrowserPreview } from "../steps/PolicyBrowserPreview";
import { StepEditor } from "../steps/StepEditor";
import { StepList } from "../steps/StepList";
import {
  getConfig,
  getCurrentRun,
  getEnvCatalog,
  getFlows,
  getRodoparMapping,
  getSteps,
  deleteRodoparFunction,
  deleteRodoparFunctionGroup,
  deleteRodoparPoint,
  saveRodoparFunction,
  saveRodoparFunctionGroup,
  saveRodoparPoint,
  saveRodoparSubTab,
  saveRodoparTab,
  startRun,
  stopRun,
  updateStep,
  type RunSnapshot,
  type RunStartPayload,
  type AppConfig,
  type EnvCatalog,
  type FlowDefinition,
  type RodoparFunctionGroup,
  type RodoparMapCatalog,
  type RodoparMapFunction,
  type RodoparMapPoint,
  type RodoparMapSubTab,
  type RodoparMapTab,
  type StepDefinition,
} from "../../lib/api";
import "./dashboard.css";

const DASHBOARD_VIEWS = [
  "execution",
  "chamados",
  "pendentes-plan",
  "mapping",
  "steps",
  "editor",
  "rodopar-control",
  "live-browser",
  "env",
] as const;

function initialDashboardView(): DashboardView {
  if (typeof window === "undefined") return "execution";
  const view = new URLSearchParams(window.location.search).get("view");
  return DASHBOARD_VIEWS.includes(view as DashboardView) ? (view as DashboardView) : "execution";
}

export function DashboardPage() {
  const [activeView, setActiveView] = useState<DashboardView>(() => initialDashboardView());
  const [steps, setSteps] = useState<StepDefinition[]>([]);
  const [selectedNumber, setSelectedNumber] = useState<number | null>(null);
  const [run, setRun] = useState<RunSnapshot | null>(null);
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [flows, setFlows] = useState<FlowDefinition[]>([]);
  const [envCatalog, setEnvCatalog] = useState<EnvCatalog | null>(null);
  const [mapping, setMapping] = useState<RodoparMapCatalog | null>(null);
  const [mappingTab, setMappingTab] = useState("Geral");
  const [mappingSubTab, setMappingSubTab] = useState("");
  const [mappingToolView, setMappingToolView] = useState<MappingToolView>("tabs");
  const [captureEnabled, setCaptureEnabled] = useState(false);
  const [pointDragEnabled, setPointDragEnabled] = useState(false);
  const [capturedPoint, setCapturedPoint] = useState<PreviewCapturePoint | null>(null);
  const [selectedMapKey, setSelectedMapKey] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const automationEvents = useAutomationEvents();

  const selectedStep = useMemo(
    () => steps.find((step) => step.number === selectedNumber) ?? steps[0] ?? null,
    [selectedNumber, steps],
  );
  const selectedMapPoint = useMemo(
    () =>
      mapping?.points.find((point) => mapPointKey(point) === selectedMapKey) ?? null,
    [mapping?.points, selectedMapKey],
  );
  const visibleMapPoints = useMemo(
    () =>
      mapping?.points.filter((point) =>
        sameMapScope(point.tab, point.sub_tab, mappingTab, mappingSubTab),
      ) ?? [],
    [mapping?.points, mappingSubTab, mappingTab],
  );
  const mapTabs = useMemo(() => {
    const names = [
      ...DEFAULT_RODOPAR_TABS,
      ...(mapping?.tabs.map((tab) => tab.name) ?? []),
      ...(mapping?.sub_tabs.map((subTab) => subTab.tab) ?? []),
      ...(mapping?.points.map((point) => point.tab) ?? []),
      ...(mapping?.function_groups.map((group) => group.tab) ?? []),
      ...(mapping?.functions.map((item) => item.tab) ?? []),
    ];
    return Array.from(new Set(names.filter(Boolean)));
  }, [mapping]);
  const envCount = useMemo(
    () =>
      Object.values(envCatalog?.groups ?? {}).reduce((total, entries) => total + entries.length, 0),
    [envCatalog?.groups],
  );

  async function refresh() {
    setError("");
    try {
      const [catalog, currentRun, flowList, envData, config, mapCatalog] = await Promise.all([
        getSteps(),
        getCurrentRun(),
        getFlows(),
        getEnvCatalog(),
        getConfig(),
        getRodoparMapping(),
      ]);
      setSteps(catalog.steps);
      setRun(currentRun);
      setFlows(flowList);
      setEnvCatalog(envData);
      setAppConfig(config);
      setMapping(mapCatalog);
      setSelectedNumber((current) => current ?? catalog.steps[0]?.number ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(number: number, patch: Partial<StepDefinition>) {
    setError("");
    try {
      const saved = await updateStep(number, patch);
      setSteps((current) => current.map((step) => (step.number === number ? saved : step)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao salvar passo.");
    }
  }

  async function handleStart(payload: RunStartPayload) {
    setError("");
    try {
      setRun(await startRun(payload));
      window.setTimeout(refresh, 600);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao iniciar.");
    }
  }

  async function handleStop() {
    setError("");
    try {
      setRun(await stopRun());
      window.setTimeout(refresh, 400);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao parar.");
    }
  }

  async function handleSaveMapPoint(point: RodoparMapPoint) {
    const saved = await saveRodoparPoint(point);
    setMapping((current) => {
      const catalog = current ?? emptyMappingCatalog();
      const points = catalog.points.filter(
        (item) => mapPointKey(item) !== mapPointKey(saved),
      );
      return { ...catalog, points: [...points, saved] };
    });
    setSelectedMapKey(mapPointKey(saved));
  }

  async function handleDeleteMapPoint(point: RodoparMapPoint) {
    const catalog = await deleteRodoparPoint(point.tab, point.id, point.sub_tab ?? "");
    setMapping(catalog);
    setSelectedMapKey("");
  }

  async function handleCreateTab(name: string) {
    const tab: RodoparMapTab = {
      id: name,
      name,
      description: "",
      order: mapTabs.length + 1,
    };
    const saved = await saveRodoparTab(tab);
    setMapping((current) => {
      const catalog = current ?? emptyMappingCatalog();
      const tabs = catalog.tabs.filter((item) => item.id !== saved.id);
      return { ...catalog, tabs: [...tabs, saved] };
    });
    setMappingTab(saved.name);
    setMappingSubTab("");
  }

  async function handleCreateSubTab(name: string) {
    const subTab: RodoparMapSubTab = {
      id: toMapId(name) || name,
      name,
      tab: mappingTab,
      description: "",
      order:
        (mapping?.sub_tabs.filter((item) => sameMapName(item.tab, mappingTab)).length ?? 0) + 1,
    };
    const saved = await saveRodoparSubTab(subTab);
    setMapping((current) => {
      const catalog = current ?? emptyMappingCatalog();
      const subTabs = catalog.sub_tabs.filter(
        (item) => !sameMapName(item.tab, saved.tab) || !sameMapName(item.id, saved.id),
      );
      return { ...catalog, sub_tabs: [...subTabs, saved] };
    });
    setMappingSubTab(saved.id);
  }

  async function handleSaveFunctionGroup(group: RodoparFunctionGroup) {
    const saved = await saveRodoparFunctionGroup(group);
    setMapping((current) => {
      const catalog = current ?? emptyMappingCatalog();
      const groups = catalog.function_groups.filter((item) => item.id !== saved.id);
      return { ...catalog, function_groups: [...groups, saved] };
    });
  }

  async function handleDeleteFunctionGroup(group: RodoparFunctionGroup) {
    setMapping(await deleteRodoparFunctionGroup(group.id));
  }

  async function handleSaveFunction(item: RodoparMapFunction) {
    const saved = await saveRodoparFunction(item);
    setMapping((current) => {
      const catalog = current ?? emptyMappingCatalog();
      const functions = catalog.functions.filter((existing) => existing.id !== saved.id);
      return { ...catalog, functions: [...functions, saved] };
    });
  }

  async function handleDeleteFunction(item: RodoparMapFunction) {
    setMapping(await deleteRodoparFunction(item.id));
  }

  async function handleMoveMapPoint(point: RodoparMapPoint, next: PreviewCapturePoint) {
    const updated = {
      ...point,
      x: next.x,
      y: next.y,
      x2: next.x2 ?? point.x2,
      y2: next.y2 ?? point.y2,
      viewport: next.viewport,
    };
    setMapping((current) => {
      if (!current) return current;
      return {
        ...current,
        points: current.points.map((item) =>
          mapPointKey(item) === mapPointKey(point) ? updated : item,
        ),
      };
    });
    setSelectedMapKey(mapPointKey(point));
    setCapturedPoint(null);
    try {
      const saved = await saveRodoparPoint(updated);
      setMapping((current) => {
        if (!current) return current;
        return {
          ...current,
          points: current.points.map((item) =>
            mapPointKey(item) === mapPointKey(saved) ? saved : item,
          ),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao mover ponto.");
    }
  }

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void getCurrentRun().then(setRun).catch(() => null);
    }, 2000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (activeView !== "mapping") {
      setCaptureEnabled(false);
      setPointDragEnabled(false);
      setCapturedPoint(null);
    }
  }, [activeView]);

  useEffect(() => {
    const event = automationEvents.events.find(
      (item) => item.run_id === run?.id && item.kind === "step.started",
    );
    const step = event?.payload?.step as { number?: unknown } | undefined;
    if (typeof step?.number === "number") setSelectedNumber(step.number);
  }, [automationEvents.events, run?.id]);

  useEffect(() => {
    if (!mappingSubTab) return;
    const exists = (mapping?.sub_tabs ?? []).some(
      (item) => sameMapName(item.tab, mappingTab) && sameMapName(item.id, mappingSubTab),
    );
    if (!exists) setMappingSubTab("");
  }, [mapping?.sub_tabs, mappingSubTab, mappingTab]);

  function handleMappingTabChange(tab: string) {
    setMappingTab(tab);
    setMappingSubTab("");
    setSelectedMapKey("");
    setPointDragEnabled(false);
    setCapturedPoint(null);
  }

  function handleMappingSubTabChange(subTab: string) {
    setMappingSubTab(subTab);
    setSelectedMapKey("");
    setPointDragEnabled(false);
    setCapturedPoint(null);
  }

  function handleCaptureChange(enabled: boolean) {
    setCaptureEnabled(enabled);
    if (enabled) setPointDragEnabled(false);
  }

  function handlePointDragChange(enabled: boolean) {
    setPointDragEnabled(enabled);
    if (enabled) {
      setCaptureEnabled(false);
      setCapturedPoint(null);
    }
  }

  function handleNavChange(view: DashboardView) {
    setActiveView(view);
    setSidebarCollapsed(true);
    const url = new URL(window.location.href);
    url.searchParams.set("view", view);
    window.history.replaceState(null, "", url.toString());
  }

  if (loading) {
    return <div className="loading-screen">Carregando automação local...</div>;
  }

  if (activeView === "live-browser") {
    // Full-window takeover, no sidebar: a native window gets reparented on
    // top of this page's toolbar area (see LiveBrowserPage/browser_embed.rs),
    // sized purely from the Tauri window's own client rect — it has no idea
    // the sidebar exists, so the sidebar can't be present here either.
    return <LiveBrowserPage onExit={() => handleNavChange("execution")} run={run} />;
  }

  return (
    <div className={sidebarCollapsed ? "dashboard dashboard-shell sidebar-collapsed" : "dashboard dashboard-shell"}>
      <DashboardNav
        activeView={activeView}
        collapsed={sidebarCollapsed}
        envCount={envCount}
        mapCount={mapping?.points.length ?? 0}
        onCollapsedChange={setSidebarCollapsed}
        onChange={handleNavChange}
        stepCount={steps.length}
      />

      <main className="dashboard-content">
        {error ? (
          <div className="error-banner">
            <AlertCircle size={18} aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        {activeView === "execution" ? (
          <div className="execution-layout">
            <RunControls
              events={automationEvents.events}
              flows={flows}
              onRefresh={refresh}
              onStart={handleStart}
              onStop={handleStop}
              run={run}
            />
            <BrowserPreview
              events={automationEvents.events}
              portalUrl={appConfig?.prePasso.url ?? ""}
              rodoparUrl={appConfig?.prePasso.rodoparUrl ?? appConfig?.prePasso.html5Url ?? ""}
              run={run}
              step={selectedStep}
            />
            <EventLog connected={automationEvents.connected} events={automationEvents.events} />
          </div>
        ) : null}

        {activeView === "chamados" ? (
          <div className="wide-page-layout">
            <ChamadosPage />
          </div>
        ) : null}

        {activeView === "pendentes-plan" ? (
          <div className="wide-page-layout">
            <PendentesPlanPage />
          </div>
        ) : null}

        {activeView === "mapping" ? (
          <div className="mapping-layout">
            <BrowserPreview
              captureEnabled={captureEnabled}
              events={automationEvents.events}
              mappedPoints={visibleMapPoints}
              onCapturePoint={(point) => setCapturedPoint(point)}
              onMoveMapPoint={handleMoveMapPoint}
              pointDragEnabled={pointDragEnabled}
              portalUrl={appConfig?.prePasso.url ?? ""}
              rodoparUrl={appConfig?.prePasso.rodoparUrl ?? appConfig?.prePasso.html5Url ?? ""}
              run={run}
              selectedMapPoint={selectedMapPoint}
              step={selectedStep}
            />
            <div className="mapping-side-column">
              <MappingToolTabs active={mappingToolView} onChange={setMappingToolView} />

              {mappingToolView === "tabs" ? (
                <MappingTabsPanel
                  onCreateSubTab={handleCreateSubTab}
                  onCreateTab={handleCreateTab}
                  onSubTabChange={handleMappingSubTabChange}
                  onTabChange={handleMappingTabChange}
                  points={mapping?.points ?? []}
                  selectedSubTab={mappingSubTab}
                  selectedTab={mappingTab}
                  subTabs={mapping?.sub_tabs ?? []}
                  tabs={mapTabs}
                />
              ) : null}

              {mappingToolView === "points" ? (
                <MapperPanel
                  captureEnabled={captureEnabled}
                  capturedPoint={capturedPoint}
                  dragEnabled={pointDragEnabled}
                  onCaptureChange={handleCaptureChange}
                  onClearCapture={() => setCapturedPoint(null)}
                  onDelete={handleDeleteMapPoint}
                  onDragChange={handlePointDragChange}
                  onSave={handleSaveMapPoint}
                  onSelectPoint={(point) => {
                    setSelectedMapKey(point ? mapPointKey(point) : "");
                    setCapturedPoint(null);
                  }}
                  points={mapping?.points ?? []}
                  selectedPoint={selectedMapPoint}
                  selectedSubTab={mappingSubTab}
                  selectedTab={mappingTab}
                />
              ) : null}

              {mappingToolView === "functions" ? (
                <MappingFunctionsPanel
                  capturedPoint={capturedPoint}
                  functions={mapping?.functions ?? []}
                  groups={mapping?.function_groups ?? []}
                  onDeleteFunction={handleDeleteFunction}
                  onDeleteGroup={handleDeleteFunctionGroup}
                  onSaveFunction={handleSaveFunction}
                  onSaveGroup={handleSaveFunctionGroup}
                  points={mapping?.points ?? []}
                  selectedPoint={selectedMapPoint}
                  selectedSubTab={mappingSubTab}
                  selectedTab={mappingTab}
                />
              ) : null}
            </div>
          </div>
        ) : null}

        {activeView === "steps" ? (
          <div className="single-page-layout">
            <StepList
              currentStep={run?.current_step}
              onSelect={(step) => setSelectedNumber(step.number)}
              selected={selectedStep}
              steps={steps}
            />
          </div>
        ) : null}

        {activeView === "editor" ? (
          <div className="editor-layout">
            <StepList
              currentStep={run?.current_step}
              onSelect={(step) => setSelectedNumber(step.number)}
              selected={selectedStep}
              steps={steps}
            />
            <StepEditor onSave={handleSave} step={selectedStep} />
          </div>
        ) : null}

        {activeView === "rodopar-control" ? (
          <div className="wide-page-layout">
            <RodoparControlPage run={run} />
          </div>
        ) : null}

        {activeView === "env" ? (
          <div className="single-page-layout">
            <EnvPanel catalog={envCatalog} />
          </div>
        ) : null}
      </main>
    </div>
  );
}
