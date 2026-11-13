export function apiErrorMessage(error: unknown, fallback = "Não foi possível confirmar o login.") {
  if (!(error instanceof Error)) return fallback;
  try {
    const parsed = JSON.parse(error.message) as { detail?: string };
    if (parsed.detail) return parsed.detail;
  } catch {
    return error.message || fallback;
  }
  return error.message || fallback;
}
