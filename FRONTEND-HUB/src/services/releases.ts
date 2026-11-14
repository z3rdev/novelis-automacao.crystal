export interface DeveloperConfig {
  enabled: boolean;
  endpoint: string;
  bucket: string;
  prefix: string;
  manifest_url: string;
}

export interface ReleaseProbe {
  authenticated: boolean;
  objects_found?: number;
  manifest_present?: boolean;
  code?: string;
  message: string;
}

export interface ReleaseManifest {
  schema_version: number;
  version: string;
  title: string;
  notes: string;
  published_at: string;
  file: string;
  sha256: string;
  size: number;
  architecture: "x64";
  object_key?: string | null;
}

export interface PublishRequest {
  installer_path: string;
  version: string;
  notes: string;
  distribution_authorized: boolean;
}

export interface PublishStatus {
  status: "idle" | "validating" | "uploading" | "publishing" | "published" | "error";
  sent_bytes: number;
  total_bytes: number;
  version: string | null;
  filename: string | null;
  message: string;
  release: ReleaseManifest | null;
}

export interface UpdateStatus {
  status:
    | "unchecked"
    | "not_published"
    | "up_to_date"
    | "available"
    | "downloading"
    | "ready"
    | "installing"
    | "error";
  current_version: string;
  release: ReleaseManifest | null;
  received_bytes: number;
  checked_at: string | null;
  message: string;
  can_install: boolean;
}
