import type { AutomationEvent } from "../../lib/api";

const WAIT_EVENTS = new Set([
  "rodopar_pdf.manual_login_confirmation_requested",
  "rodopar_pdf.html5_detected_pause",
  "rodopar_pdf.waiting_blue_screen",
  "rodopar_pdf.waiting_manual_login",
]);

const CONFIRM_EVENTS = new Set([
  "rodopar_pdf.manual_login_confirmed",
  "rodopar_pdf.manual_login_ready",
]);

export function isRodoparWaitEvent(event: AutomationEvent, runId?: string) {
  return event.run_id === runId && WAIT_EVENTS.has(event.kind);
}

export function isRodoparConfirmEvent(event: AutomationEvent, runId?: string) {
  return event.run_id === runId && CONFIRM_EVENTS.has(event.kind);
}
