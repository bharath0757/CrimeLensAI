/**
 * CrimeLensAI — API Client
 * =========================
 * Centralized HTTP client for communicating with the API Gateway / FastAPI backend.
 *
 * All API calls from the frontend go through this client, which handles:
 * - Base URL configuration (from environment variable)
 * - JWT token injection for authenticated requests
 * - Consistent error handling
 * - Request/response typing using shared types
 * - Resilient fallback data so pages never fail to render
 *
 * Uses the platform adapter for token storage so it works on both
 * web (localStorage) and mobile (Capacitor Preferences).
 */

import { platform } from "../adapters/platform";
import type { AuthToken, CaseInput, CaseRecord, EvidenceDocument, ExtractionPreview, ProcessResult, UserProfile } from "./contracts";
import { SESSION_EXPIRED_EVENT } from "./auth-events";
import type { DashboardOverview, DashboardMetrics, ConnectionAlert, ConnectionAlertPage } from "./contracts";
import type { CaseLinkageResponse } from "./contracts";
import type { IngestionReceipt } from "./contracts";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");
const TOKEN_KEY = "crimelens_auth_token";

/**
 * Generic API response wrapper.
 */
interface ApiError {
  status: number;
  message: string;
  errors?: string[];
  detail?: unknown;
}

export function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null && "message" in error && typeof error.message === "string") {
    return error.message;
  }
  return "The request could not be completed. Please try again.";
}


/**
 * Make an authenticated API request.
 */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await platform.storage.get(TOKEN_KEY);

  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    // Catch unhandled network errors (e.g. backend unreachable, CORS failure)
    throw {
      status: 0,
      message: "Unable to connect to CrimeLensAI services. Please check if the backend is running.",
      errors: [errorMessage(err)],
    } as ApiError;
  }

  if (!response.ok) {
    if (response.status === 401 && token && !path.startsWith("/api/v1/auth/login")) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
    }
    const error: ApiError = {
      status: response.status,
      message: response.statusText,
    };
    try {
      const body = await response.json();
      error.message = typeof body.detail === "string" ? body.detail : (body.message || response.statusText);
      if (Array.isArray(body.detail)) {
        error.message = body.detail.map((item: { loc?: string[]; msg?: string }) =>
          `${item.loc?.slice(1).join(".") || "Input"}: ${item.msg || "Invalid value"}`
        ).join("; ");
      }
      error.detail = body.detail;
      error.errors = body.errors;
    } catch {
      // Response body wasn't JSON — use statusText
    }
    throw error;
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function download(path: string): Promise<{ blob: Blob; filename: string; sha256: string; auditEventId: string }> {
  const token = await platform.storage.get(TOKEN_KEY);
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers });
  } catch (error) {
    throw { status: 0, message: "Unable to connect to CrimeLensAI services.", errors: [errorMessage(error)] } as ApiError;
  }
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the HTTP status text for non-JSON failures.
    }
    throw { status: response.status, message } as ApiError;
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || "crimelens-evidence-report.pdf";
  return {
    blob: await response.blob(),
    filename,
    sha256: response.headers.get("X-Report-SHA256") || "",
    auditEventId: response.headers.get("X-Audit-Event-ID") || "",
  };
}

// ---- API Client Methods ----

export const api = {
  // Health
  health: () => request<{ status: string }>("/health"),

  // Cases
  cases: {
    metadata: (skip = 0, limit = 100, search = "", signal?: AbortSignal) => request<{ total: number; items: CaseRecord[] }>(`/api/v1/cases?skip=${skip}&limit=${limit}&search=${encodeURIComponent(search)}`, { signal }),
    list: async (skip = 0, limit = 50) => {
      try {
        const response: any = await request(`/api/v1/cases?skip=${skip}&limit=${limit}`);
        const items = Array.isArray(response) ? response : (response?.items || []);

        const enrichedItems = await Promise.all(
          items.map(async (c: any) => {
            const caseId = c.id || c._id;
            if (!caseId) return c;
            if (Array.isArray(c.entities) && c.entities.length > 0) return c;

            try {
              const entResponse: any = await request(`/api/v1/cases/${caseId}/entities`);
              const entList = Array.isArray(entResponse) ? entResponse : (entResponse?.items || []);
              
              const formattedEntities = entList.map((e: any) => {
                let entityType = e.entity_type || e.type || "OTHER";
                if (entityType === "PHONE_NUMBER") entityType = "PHONE";
                if (entityType === "ORGANIZATION") entityType = "ORG";

                return {
                  id: e.id,
                  value: e.name || e.value,
                  type: entityType,
                  confidence: e.confidence_score ?? e.confidence ?? 1.0,
                  status: e.status || "PENDING",
                };
              });

              return { ...c, entities: formattedEntities };
            } catch {
              return { ...c, entities: c.entities || [] };
            }
          })
        );

        const resultItems = enrichedItems;

        return Array.isArray(response)
          ? resultItems
          : { total: response.total, skip, limit, items: resultItems };
      } catch (err) {
        throw err;
      }
    },

    get: (id: string) => request<CaseRecord>(`/api/v1/cases/${id}`),

    create: (data: CaseInput) => request<CaseRecord>("/api/v1/cases", {
      method: "POST", body: JSON.stringify(data),
    }),

    update: (id: string, data: unknown) =>
      request(`/api/v1/cases/${id}`, { method: "PUT", body: JSON.stringify(data) }),

    delete: (id: string) =>
      request(`/api/v1/cases/${id}`, { method: "DELETE" }),
  },

  // Search
  search: (q: string, entityType?: string) => {
    const params = new URLSearchParams({ q });
    if (entityType) params.set("entity_type", entityType);
    return request(`/api/v1/search/global?${params}`);
  },

  // Ingestion
  ingestion: {
    upload: (caseId: string, kind: "cdr" | "transactions", file: File) => {
      const body = new FormData();
      body.append("file", file);
      return request<IngestionReceipt>(`/api/v1/cases/${encodeURIComponent(caseId)}/ingestion/csv?kind=${kind}`, { method: "POST", body });
    },
    status: (caseId: string, batchId: string, signal?: AbortSignal) => request<IngestionReceipt>(`/api/v1/cases/${encodeURIComponent(caseId)}/ingestion/${encodeURIComponent(batchId)}`, { signal }),
  },
  ingest: (data: unknown) =>
    request("/api/v1/ingest", { method: "POST", body: JSON.stringify(data) }),

  // Dashboard
  dashboard: {
    stats: (signal?: AbortSignal) => request<DashboardMetrics>("/api/v1/dashboard/stats", { signal }),
    overview: (signal?: AbortSignal) => request<DashboardOverview>("/api/v1/dashboard/overview", { signal }),
    alerts: (signal?: AbortSignal, offset = 0) => request<ConnectionAlertPage>(`/api/v1/dashboard/alerts?offset=${offset}&limit=20`, { signal }),
    acknowledge: (id: string) => request<ConnectionAlert>(`/api/v1/dashboard/alerts/${encodeURIComponent(id)}/acknowledge`, { method: "POST" }),
  },

  extraction: {
    preview: (text: string, signal?: AbortSignal) => request<ExtractionPreview>("/api/v1/extraction/preview", {
      method: "POST", body: JSON.stringify({ text }), signal,
    }),
    previewFile: (file: File, signal?: AbortSignal) => {
      const body = new FormData();
      body.append("file", file);
      return request<ExtractionPreview>("/api/v1/extraction/preview-file", { method: "POST", body, signal });
    },
  },

  documents: {
    upload: (caseId: string, file: File) => {
      const body = new FormData();
      body.append("file", file);
      return request<EvidenceDocument>(`/api/v1/cases/${caseId}/documents`, { method: "POST", body });
    },
    process: (id: string) => request<ProcessResult>(`/api/v1/documents/${id}/process`, { method: "POST" }),
    get: (id: string) => request<EvidenceDocument>(`/api/v1/documents/${id}`),
  },

  // Entities
  graph: {
    getCaseGraph: (caseId: string) => request(`/api/v1/cases/${caseId}/graph`),
    getCaseLinkage: (caseId: string) => request<CaseLinkageResponse>(`/api/v1/cases/${caseId}/linkage`),
  },

  // Entities
  entities: {
    confirm: (id: string) => request(`/api/v1/entities/${id}/confirm`, { method: "POST" }),
    reject: (id: string) => request(`/api/v1/entities/${id}/reject`, { method: "POST" }),
  },

  // Auth
  auth: {
    login: async (username: string, password: string) => {
      const emailCandidate = username.includes("@") ? username : `${username}@crimelens.ai`;
      
      try {
        const res = await request<AuthToken>("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: emailCandidate, password }),
        });
        if (res?.access_token) {
          return res;
        }
      } catch (err) {
        throw err;
      }
      
      throw new Error("Invalid response from server");
    },

    me: async () => request<UserProfile>("/api/v1/auth/me"),

    setToken: async (token: string) => {
      await platform.storage.set(TOKEN_KEY, token);
    },

    clearToken: async () => {
      await platform.storage.remove(TOKEN_KEY);
    },
  },

  // Ledger / Audit
  ledger: {
    chain: (limit = 50, offset = 0, caseId = "") => request(`/api/v1/ledger/chain?limit=${limit}&offset=${offset}${caseId ? `&case_id=${encodeURIComponent(caseId)}` : ""}`),
    verify: (recordId: string, caseId = "") => request(`/api/v1/ledger/verify/${recordId}${caseId ? `?case_id=${encodeURIComponent(caseId)}` : ""}`),
  },

  reports: {
    downloadEvidence: (caseId: string) => download(`/api/v1/cases/${encodeURIComponent(caseId)}/evidence-report.pdf`),
  },
};

export default api;
