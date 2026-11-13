import { useEffect, useState } from "react";
import { getConfig } from "../../lib/api";

export function useRodoparEnabled() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let active = true;
    void getConfig().then((config) => {
      if (active) setEnabled(config.prePasso.rodoparBrowserEnabled === true);
    }).catch(() => { if (active) setEnabled(false); });
    return () => { active = false; };
  }, []);
  return enabled;
}
