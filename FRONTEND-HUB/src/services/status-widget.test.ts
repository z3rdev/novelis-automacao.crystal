import { describe, expect, it } from "vitest";
import type { AutomationSchedule, RunStatus } from "./types";
import { makeWidgetSnapshot, widgetMotion, widgetStatus, widgetStaleAfter } from "./status-widget";

const now = Date.parse("2026-11-15T12:00:00-03:00");
const run: RunStatus = {
  id: "run-1",
  flow: "completo",
  state: "executando",
  etapaAtual: "pdf",
  cteAtual: "1-10-123",
  processados: 2,
  total: 5,
  iniciadoEm: "2026-11-15T11:59:00-03:00",
  stages: [],
};
const schedule: AutomationSchedule = {
  id: "s1",
  revision: 1,
  name: "Rotina diária",
  time: "13:00",
  weekdays: [0],
  flow: "completo",
  days_back: 2,
  enabled: true,
  operator_name: "Operador",
  activated_at: "2026-11-15T10:00:00-03:00",
  next_run_at: "2026-11-15T13:00:00-03:00",
  last_run: null,
};

describe("estado do widget de agendamentos", () => {
  it("usa a próxima rotina ativa e a etapa real do fluxo", () => {
    const value = makeWidgetSnapshot({
      run,
      schedules: {
        schedules: [
          {
            ...schedule,
            id: "disabled",
            name: "Desativada",
            enabled: false,
            next_run_at: "2026-11-15T12:01:00-03:00",
          },
          { ...schedule, id: "later", next_run_at: "2026-11-15T14:00:00-03:00" },
          schedule,
        ],
        device: "TEST-PC",
        local_time: "",
        running: true,
      },
      connection: "connected",
      now,
    });
    expect(value.next?.at).toBe(schedule.next_run_at);
    expect(value.activeSchedules).toBe(2);
    expect(value.done).toBe(2);
    expect(widgetStatus(value, now).label).toBe("Gerando PDF");
  });
  it("atualiza o rótulo de uma etapa personalizada e preserva a tentativa programada", () => {
    const value = makeWidgetSnapshot({
      run: {
        ...run,
        workflow: {
          name: "Meu fluxo",
          current_node_id: "tarifa",
          completed: 0,
          total: 1,
          completion: null,
          nodes: [
            {
              id: "tarifa",
              kind: "tariffs",
              label: "Atualizar tarifário",
              state: "executando",
              options: { start_days_ago: 0, end_days_ago: 0 },
              done: 0,
              total: 1,
              detail: "Consultando portal",
              started_at: null,
              finished_at: null,
            },
          ],
        },
      },
      schedules: { schedules: [{ ...schedule, next_attempt: 2 }], device: "", local_time: "" },
      connection: "connected",
      now,
    });
    expect(value.activity).toBe("Atualizando tarifário");
    expect(value.detail).toBe("Consultando portal");
    expect(value.next?.attempt).toBe(2);
  });
  it("sinaliza perda de conexão e dados antigos enquanto havia execução", () => {
    const value = makeWidgetSnapshot({ run, schedules: undefined, connection: "connected", now });
    expect(widgetStatus(value, now + widgetStaleAfter + 1).connected).toBe(false);
    expect(widgetStatus({ ...value, connection: "offline" }, now).label).toBe("Reconectando");
    expect(widgetStatus({ ...value, connection: "login_required" }, now).label).toBe(
      "Entre no Cargo Hub",
    );
  });
  it("informa falha, agendador parado e ausência de rotinas", () => {
    const value = makeWidgetSnapshot({
      run: { ...run, state: "falhou" },
      schedules: { schedules: [], device: "", local_time: "", running: false },
      connection: "connected",
      now,
    });
    expect(widgetStatus(value, now).label).toBe("Falha na execução");
    expect(widgetStatus({ ...value, state: "aguardando" }, now).label).toBe("Agendador inativo");
    expect(value.next).toBeNull();
  });
  it("anima a etapa real e prioriza falha e perda de atualização", () => {
    const value = makeWidgetSnapshot({ run, schedules: undefined, connection: "connected", now });
    expect(widgetMotion(value, now)).toBe("generate");
    const xml = makeWidgetSnapshot({
      run: { ...run, etapaAtual: "xml" },
      schedules: undefined,
      connection: "connected",
      now,
    });
    expect(widgetMotion(xml, now)).toBe("download");
    const validating = makeWidgetSnapshot({
      run: {
        ...run,
        stages: [
          {
            id: "pdf",
            state: "executando",
            done: 0,
            total: 1,
            atividade: "Validando códigos do PDF",
          },
        ],
      },
      schedules: undefined,
      connection: "connected",
      now,
    });
    expect(widgetMotion(validating, now)).toBe("validate");
    expect(widgetMotion({ ...value, activityKind: "verify" }, now)).toBe("verify");
    expect(widgetMotion({ ...value, state: "falhou" }, now)).toBe("error");
    expect(widgetMotion({ ...value, state: "concluida" }, now)).toBe("success");
    expect(widgetMotion(value, now + widgetStaleAfter + 1)).toBe("connect");
    const legacy = { ...value, activity: "Baixando XML" };
    delete legacy.activityKind;
    expect(widgetMotion(legacy, now)).toBe("download");
  });
});
