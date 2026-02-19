import { AnalysisPoint, AlertItem, FieldSummary, IndexName } from "@fieldmonitor/shared-types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8002";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface OrganizationItem {
  id: string;
  name: string;
  created_at: string;
}

export interface FarmItem {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  created_at: string;
}

function buildErrorMessage(status: number, body: string): string {
  const fallback = body || `Request failed (${status})`;
  try {
    const parsed = JSON.parse(body) as { detail?: string | Array<{ loc?: unknown; msg?: unknown }> };
    const detail = parsed?.detail;
    if (typeof detail === "string" && detail) {
      return `Request failed (${status}): ${detail}`;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0];
      const msg = typeof first?.msg === "string" ? first.msg : "Validation error";
      const loc = Array.isArray(first?.loc) ? first.loc.filter((part) => typeof part === "string").join(".") : "";
      const context = loc ? `${loc}: ${msg}` : msg;
      return `Request failed (${status}): ${context}`;
    }
    return fallback;
  } catch {
    return fallback;
  }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", headers.get("Content-Type") ?? "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers, cache: "no-store" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(buildErrorMessage(response.status, text));
  }
  return (await response.json()) as T;
}

export async function registerAuth(payload: {
  email: string;
  password: string;
  full_name?: string;
}): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function loginAuth(payload: { email: string; password: string }): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createOrganization(payload: { name: string }, token: string): Promise<OrganizationItem> {
  return request<OrganizationItem>(
    "/api/v1/orgs",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export async function listFarms(token: string): Promise<FarmItem[]> {
  return request<FarmItem[]>("/api/v1/farms", {}, token);
}

export async function createFarm(
  payload: { organization_id: string; name: string; description?: string },
  token: string,
): Promise<FarmItem> {
  return request<FarmItem>(
    "/api/v1/farms",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export interface StartAnalysisPayload {
  scene_id?: string;
  date_from?: string;
  date_to?: string;
  max_cloud?: number;
  include_sr?: boolean;
  include_radar_overlay?: boolean;
}

export interface AnalysisJob {
  id: string;
  status: string;
  queue: string;
}

export interface ExportJob {
  id: string;
  status: string;
  format: string;
  output_uri?: string;
  error_message?: string;
}

export interface TimelineClearResult {
  field_id: string;
  deleted_observations: number;
  deleted_scene_candidates: number;
  deleted_analysis_jobs: number;
  deleted_layer_assets: number;
  deleted_total: number;
}

export interface AlertsClearResult {
  deleted_alerts: number;
}

export interface ImageryItem {
  scene_id: string;
  acquisition_date: string;
  cloud_cover?: number;
  provider: string;
  collection: string;
  bbox?: number[] | null;
  footprint_geojson?: GeoJSON.Geometry | null;
  preview_url?: string | null;
  field_coverage_ratio?: number | null;
}

export async function createField(
  payload: { farm_id: string; name: string; geometry: GeoJSON.Geometry },
  token: string,
): Promise<FieldSummary> {
  return request<FieldSummary>("/api/v1/fields", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export async function listFields(
  params: { farm_id?: string } = {},
  token?: string,
): Promise<FieldSummary[]> {
  const query = new URLSearchParams();
  if (params.farm_id) query.set("farm_id", params.farm_id);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<FieldSummary[]>(`/api/v1/fields${suffix}`, {}, token);
}

export async function updateFieldSchedule(
  fieldId: string,
  payload: { enabled: boolean; timezone: string; local_time: string; frequency: "daily" | "weekly" },
  token: string,
): Promise<FieldSummary> {
  return request<FieldSummary>(
    `/api/v1/fields/${fieldId}/schedule`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
    token,
  );
}

export async function importField(
  payload: { farm_id: string; name: string; file: File },
  token: string,
): Promise<FieldSummary> {
  const data = new FormData();
  data.set("farm_id", payload.farm_id);
  data.set("name", payload.name);
  data.set("file", payload.file);

  const response = await fetch(`${API_BASE}/api/v1/fields/import`, {
    method: "POST",
    body: data,
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(buildErrorMessage(response.status, text));
  }
  return (await response.json()) as FieldSummary;
}

export async function searchImagery(
  fieldId: string,
  params: { date_from?: string; date_to?: string; max_cloud?: number },
  token: string,
): Promise<ImageryItem[]> {
  const query = new URLSearchParams();
  if (params.date_from) query.set("date_from", params.date_from);
  if (params.date_to) query.set("date_to", params.date_to);
  if (params.max_cloud !== undefined) query.set("max_cloud", String(params.max_cloud));
  return request<ImageryItem[]>(`/api/v1/fields/${fieldId}/imagery/search?${query.toString()}`, {}, token);
}

export async function startAnalysis(fieldId: string, payload: StartAnalysisPayload, token: string): Promise<AnalysisJob> {
  return request<AnalysisJob>(`/api/v1/fields/${fieldId}/analyses`, {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export async function getTimeseries(
  fieldId: string,
  index: IndexName,
  token: string,
): Promise<{ field_id: string; points: AnalysisPoint[] }> {
  return request<{ field_id: string; points: AnalysisPoint[] }>(
    `/api/v1/fields/${fieldId}/timeseries?index=${index}`,
    {},
    token,
  );
}

export async function clearFieldTimeline(fieldId: string, token: string): Promise<TimelineClearResult> {
  return request<TimelineClearResult>(`/api/v1/fields/${fieldId}/timeseries`, { method: "DELETE" }, token);
}

export async function listAlerts(token: string): Promise<AlertItem[]> {
  return request<AlertItem[]>("/api/v1/alerts", {}, token);
}

export async function clearAlerts(
  token: string,
  params: { field_id?: string } = {},
): Promise<AlertsClearResult> {
  const query = new URLSearchParams();
  if (params.field_id) query.set("field_id", params.field_id);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<AlertsClearResult>(`/api/v1/alerts${suffix}`, { method: "DELETE" }, token);
}

export async function ackAlert(alertId: string, token: string): Promise<AlertItem> {
  return request<AlertItem>(`/api/v1/alerts/${alertId}/ack`, { method: "POST", body: "{}" }, token);
}

export async function createExport(
  payload: {
    field_id: string;
    format: "CSV" | "PNG" | "GEOTIFF";
    layer_id?: string;
    index_name?: string;
    source_mode?: "native" | "sr";
  },
  token: string,
): Promise<ExportJob> {
  return request<ExportJob>("/api/v1/exports", {
    method: "POST",
    body: JSON.stringify(payload),
  }, token);
}

export async function getExportJob(exportId: string, token: string): Promise<ExportJob> {
  return request<ExportJob>(`/api/v1/exports/${exportId}`, {}, token);
}
