/**
 * CrimeLensAI — API Client
 * =========================
 * Centralized HTTP client for communicating with the API Gateway.
 *
 * All API calls from the frontend go through this client, which handles:
 * - Base URL configuration (from environment variable)
 * - JWT token injection for authenticated requests
 * - Consistent error handling
 * - Request/response typing using shared types
 *
 * Uses the platform adapter for token storage so it works on both
 * web (localStorage) and mobile (Capacitor Preferences).
 */

import { platform } from "../adapters/platform";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "crimelens_auth_token";

/**
 * Generic API response wrapper.
 */
interface ApiError {
  status: number;
  message: string;
  errors?: string[];
}

/**
 * Make an authenticated API request.
 */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await platform.storage.get(TOKEN_KEY);

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (err: any) {
    // Catch unhandled network errors (e.g. backend unreachable, CORS failure)
    throw {
      status: 0,
      message: "Unable to connect to CrimeLensAI services. Please check if the backend is running.",
      errors: [err.message || "Failed to fetch"],
    } as ApiError;
  }

  if (!response.ok) {
    const error: ApiError = {
      status: response.status,
      message: response.statusText,
    };
    try {
      const body = await response.json();
      error.message = body.detail || body.message || response.statusText;
      error.errors = body.errors;
    } catch {
      // Response body wasn't JSON — use statusText
    }
    throw error;
  }

  return response.json() as Promise<T>;
}

// ---- API Client Methods ----

export const api = {
  // Health
  health: () => request<{ status: string }>("/api/v1/health"),

  // Cases
  cases: {
    list: (skip = 0, limit = 20) =>
      request(`/api/v1/cases?skip=${skip}&limit=${limit}`),
    get: (id: string) => request(`/api/v1/cases/${id}`),
    create: (data: unknown) =>
      request("/api/v1/cases", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: unknown) =>
      request(`/api/v1/cases/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    delete: (id: string) =>
      request(`/api/v1/cases/${id}`, { method: "DELETE" }),
  },

  // Search
  search: (q: string, entityType?: string) => {
    const params = new URLSearchParams({ q });
    if (entityType) params.set("entity_type", entityType);
    return request(`/api/v1/search?${params}`);
  },

  // Ingestion
  ingest: (data: unknown) =>
    request("/api/v1/ingest", { method: "POST", body: JSON.stringify(data) }),

  // Dashboard
  dashboard: {
    stats: () => request("/api/v1/dashboard/stats"),
  },

  // Entities
  entities: {
    confirm: (id: string) =>
      request(`/api/v1/entities/${id}/confirm`, { method: "POST" }),
    reject: (id: string) =>
      request(`/api/v1/entities/${id}/reject`, { method: "POST" }),
  },

  // Graph & Network Analysis
  graph: {
    get: (caseId: string) => request(`/api/v1/cases/${caseId}/graph`),
    stats: (caseId: string) => request(`/api/v1/cases/${caseId}/graph/stats`),
  },

  // Documents
  documents: {
    list: (caseId: string) => request(`/api/v1/cases/${caseId}/documents`),
    get: (documentId: string) => request(`/api/v1/documents/${documentId}`),
  },

  // Auth
  auth: {
    login: (username: string, password: string) =>
      request("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: username, username, password }),
      }),
    me: () => request("/api/v1/auth/me"),
    setToken: async (token: string) => {
      await platform.storage.set(TOKEN_KEY, token);
    },
    clearToken: async () => {
      await platform.storage.remove(TOKEN_KEY);
    },
  },

  // Ledger / Audit
  ledger: {
    chain: (limit = 50, offset = 0) =>
      request(`/api/v1/ledger/chain?limit=${limit}&offset=${offset}`),
    verify: (recordId: string) =>
      request(`/api/v1/ledger/verify/${recordId}`),
  },
};

export default api;
