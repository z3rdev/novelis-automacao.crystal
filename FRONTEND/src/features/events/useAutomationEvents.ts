import { useEffect, useState } from "react";

import { API_BASE, type AutomationEvent } from "../../lib/api";

export function useAutomationEvents() {
  const [events, setEvents] = useState<AutomationEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/events`);

    source.addEventListener("open", () => setConnected(true));
    source.addEventListener("error", () => setConnected(false));
    source.addEventListener("automation", (event) => {
      const parsed = JSON.parse((event as MessageEvent).data) as AutomationEvent;
      setEvents((current) => [parsed, ...current].slice(0, 160));
    });

    return () => source.close();
  }, []);

  return { events, connected };
}
