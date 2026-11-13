import { Terminal } from "lucide-react";

import type { AutomationEvent } from "../../lib/api";
import { useAutomationEvents } from "./useAutomationEvents";

interface Props {
  connected?: boolean;
  events?: AutomationEvent[];
}

export function EventLog(props: Props = {}) {
  const live = useAutomationEvents();
  const events = props.events ?? live.events;
  const connected = props.connected ?? live.connected;

  return (
    <section className="panel event-panel">
      <div className="panel-title">
        <Terminal size={18} aria-hidden="true" />
        <h2>Eventos</h2>
        <span className={connected ? "pill ok" : "pill warn"}>
          {connected ? "online" : "offline"}
        </span>
      </div>
      <div className="event-list">
        {events.length === 0 ? (
          <p className="muted">Nenhum evento recebido.</p>
        ) : (
          events.map((event) => (
            <article className={`event-row ${event.level}`} key={event.id}>
              <time>{new Date(event.created_at).toLocaleTimeString("pt-BR")}</time>
              <strong>{event.kind}</strong>
              <span>{event.message}</span>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
