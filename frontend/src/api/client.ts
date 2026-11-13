import type { components } from "./schema";

export interface ErrorEnvelope {
  code: string;
  message: string;
  details?: Record<string, unknown> | unknown[] | null;
}

export type ValidationReport = components["schemas"]["ValidationReport"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type ModelInfoResponse = components["schemas"]["ModelInfoResponse"];
export type CascadeSummaryItem = components["schemas"]["CascadeSummaryItem"];
export type CascadeListResponse = components["schemas"]["CascadeListResponse"];
export type TreeNodePayload = components["schemas"]["TreeNodePayload"];
export type TreeEdgePayload = components["schemas"]["TreeEdgePayload"];
export type TreeGraphResponse = components["schemas"]["TreeGraphResponse"];
export type FeatureFactor = components["schemas"]["FeatureFactor"];
export type PredictCascadeResult = components["schemas"]["PredictCascadeResult"];
export type PredictResponse = components["schemas"]["PredictResponse"];
export type ValidateResponse = components["schemas"]["ValidateResponse"];
export type ModelMetricsEntry = components["schemas"]["ModelMetricsEntry"];
export type FeatureImportanceEntry = components["schemas"]["FeatureImportanceEntry"];
export type ThresholdSensitivityEntry = components["schemas"]["ThresholdSensitivityEntry"];
export type ReportResponse = components["schemas"]["ReportResponse"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const contentType = res.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const body = isJson ? await res.json() : null;

  if (!res.ok) {
    if (body && typeof body === "object" && "code" in body && "message" in body) {
      const env = body as ErrorEnvelope;
      throw new ApiError(res.status, env.code, env.message, env.details);
    }
    throw new ApiError(res.status, "HTTP_ERROR", `Request failed with status ${res.status}.`);
  }
  return body as T;
}

export const api = {
  getHealth: (): Promise<HealthResponse> => requestJson<HealthResponse>("/api/health"),

  getModelInfo: (): Promise<ModelInfoResponse> =>
    requestJson<ModelInfoResponse>("/api/model/info"),

  getCascades: (params: {
    limit?: number;
    offset?: number;
    search?: string;
  }): Promise<CascadeListResponse> => {
    const qs = new URLSearchParams();
    if (params.limit !== undefined) qs.set("limit", String(params.limit));
    if (params.offset !== undefined) qs.set("offset", String(params.offset));
    if (params.search && params.search.trim()) qs.set("search", params.search.trim());
    return requestJson<CascadeListResponse>(`/api/cascades?${qs.toString()}`);
  },

  getCascadeTree: (cascadeId: string): Promise<TreeGraphResponse> =>
    requestJson<TreeGraphResponse>(`/api/cascades/${encodeURIComponent(cascadeId)}`),

  validateCsv: (file: File): Promise<ValidateResponse> => {
    const form = new FormData();
    form.append("file", file);
    return requestJson<ValidateResponse>("/api/validate", { method: "POST", body: form });
  },

  predictById: (cascadeId: string): Promise<PredictResponse> =>
    requestJson<PredictResponse>("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cascade_id: cascadeId }),
    }),

  predictCsv: (file: File): Promise<PredictResponse> => {
    const form = new FormData();
    form.append("file", file);
    return requestJson<PredictResponse>("/api/predict", { method: "POST", body: form });
  },

  getReport: (): Promise<ReportResponse> => requestJson<ReportResponse>("/api/report"),
};
