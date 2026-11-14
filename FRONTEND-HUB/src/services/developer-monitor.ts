export interface MonitoredDevice {
  id: string;
  machine_id: string;
  computer_name: string;
  windows_user: string;
  mac_addresses: string[];
  version: string | null;
  installation_kind: "installed" | "development" | "unreported";
  install_root: string | null;
  first_seen_at: string | null;
  last_seen_at: string;
  backend_started_at: string | null;
  backend_status: string;
  automation_status: string;
  run_id: string | null;
  online: boolean;
  operators: string[];
}

export interface MonitoredSession {
  id: string;
  machine_id: string;
  operator_name: string;
  windows_user: string;
  computer_name: string;
  mac_addresses: string[];
  login_at: string;
  last_seen_at: string;
  logout_at: string | null;
  status: string;
  display_status: string;
  automation_status: string;
  run_id: string | null;
  online: boolean;
}

export interface DeveloperMonitor {
  checked_at: string;
  online_timeout_seconds: number;
  source: string;
  truncated: boolean;
  local_pending_sync: number;
  devices: MonitoredDevice[];
  sessions: MonitoredSession[];
  summary: {
    detected_installations: number;
    online_devices: number;
    logged_in_users: number;
    running_automations: number;
    broken_automations: number;
  };
}
