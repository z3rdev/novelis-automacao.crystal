export interface MasterAccessState {
  configured: boolean;
  can_setup: boolean;
  unlocked: boolean;
  expires_at: string | null;
}

export interface MasterPolicyState {
  configured: boolean;
  updated_at: string | null;
  updated_by: string | null;
}
