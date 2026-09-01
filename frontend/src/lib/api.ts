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

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "crimelens_auth_token";

/**
 * Generic API response wrapper.
 */
interface ApiError {
  status: number;
  message: string;
  errors?: string[];
  detail?: any;
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
      error.message = typeof body.detail === "string" ? body.detail : (body.message || response.statusText);
      error.detail = body.detail;
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
  health: () => request<{ status: string }>("/health"),

  // Cases
  cases: {
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
                if (entityType === "BANK_ACCOUNT") entityType = "UPI_ID";

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
          : { total: resultItems.length, skip, limit, items: resultItems };
      } catch (err) {
        throw err;
      }
    },

    get: (id: string) => request(`/api/v1/cases/${id}`),

    create: async (data: any) => {
      const tags = [
        ...(data.category ? [data.category] : []),
        ...(data.district ? [data.district] : []),
        ...(Array.isArray(data.tags) ? data.tags : []),
      ];

      const casePayload = {
        title: data.title || "Untitled Case",
        description: data.firText || data.description || "No narrative provided",
        case_number: data.firNumber || data.case_number || undefined,
        tags: tags.length > 0 ? tags : undefined,
        priority: data.priority || "MEDIUM",
      };

            const createdCase = await request<any>("/api/v1/cases", {
        method: "POST",
        body: JSON.stringify(casePayload),
      });

      const createdCaseId = createdCase?.id;
      if (createdCaseId && Array.isArray(data.entities)) {
        for (const ent of data.entities) {
          let entType = ent.type;
          if (entType === "PHONE") entType = "PHONE_NUMBER";
          if (entType === "ORG") entType = "ORGANIZATION";
          if (entType === "UPI_ID") entType = "BANK_ACCOUNT";

          await request(`/api/v1/cases/${createdCaseId}/entities`, {
            method: "POST",
            body: JSON.stringify({
              name: ent.value || ent.name,
              entity_type: entType || "OTHER",
              confidence_score: ent.confidence ?? 1.0,
            }),
          });
        }
      }

      return createdCase;
    },

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
  ingest: (data: unknown) =>
    request("/api/v1/ingest", { method: "POST", body: JSON.stringify(data) }),

  // Dashboard
  dashboard: {
    stats: async () => {
      const data: any = await request("/api/v1/dashboard/stats");
      return {
        totalCases: data.totalCases ?? data.total_cases ?? 0,
        entitiesExtracted: data.entitiesExtracted ?? data.total_entities ?? 0,
        crossCaseLinks: data.crossCaseLinks ?? data.total_relationships ?? 0,
        pendingReviews: data.pendingReviews ?? data.pending_reviews ?? 0,
      };
    },
  },

  // Entities
  graph: {
    getCaseGraph: (caseId: string) => request(`/api/v1/cases/${caseId}/graph`),
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
        const res: any = await request("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: emailCandidate, password }),
        });
        if (res && (res.access_token || res.token)) {
          return res;
        }
      } catch (err) {
        throw err;
      }
      
      throw new Error("Invalid response from server");
    },

    me: async () => request("/api/v1/auth/me"),

    setToken: async (token: string) => {
      await platform.storage.set(TOKEN_KEY, token);
    },

    clearToken: async () => {
      await platform.storage.remove(TOKEN_KEY);
    },
  },

  // Ledger / Audit
  ledger: {
    chain: (limit = 50, offset = 0) => request(`/api/v1/ledger/chain?limit=${limit}&offset=${offset}`),
    verify: (recordId: string) => request(`/api/v1/ledger/verify/${recordId}`),
  },
};

export default api;
