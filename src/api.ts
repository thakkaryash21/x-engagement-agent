import type {
  DraftsResponse,
  IncidentsResponse,
  InsightsResponse,
  KnowledgeResponse,
  PersonaResponse,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || `${response.status} ${url}`);
  }
  return data as T;
}

export const api = {
  drafts: () => request<DraftsResponse>("/api/drafts"),
  incidents: () => request<IncidentsResponse>("/api/incidents"),
  clearLockout: () => request<{ ok: boolean; cleared: boolean }>("/api/incidents/clear-lockout", { method: "POST", body: "{}" }),
  approveDraft: (id: string, editedText: string) =>
    request<{ ok: boolean; status: string }>(`/api/drafts/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      body: JSON.stringify({ edited_text: editedText }),
    }),
  discardDraft: (id: string, reason: string) =>
    request<{ ok: boolean }>(`/api/drafts/${encodeURIComponent(id)}/discard`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  insights: () => request<InsightsResponse>("/api/insights"),
  limits: () => request<Record<string, number>>("/api/config/limits"),
  saveLimits: (updates: Record<string, number>) =>
    request<Record<string, number>>("/api/config/limits", { method: "POST", body: JSON.stringify(updates) }),
  metrics: () => request<Record<string, string[]>>("/api/config/metrics"),
  saveMetrics: (updates: Record<string, string[]>) =>
    request<Record<string, string[]>>("/api/config/metrics", { method: "POST", body: JSON.stringify(updates) }),
  persona: () => request<PersonaResponse>("/api/config/persona"),
  savePersona: (persona: string, tagging: "on" | "off") =>
    request<PersonaResponse["active"]>("/api/config/persona", { method: "POST", body: JSON.stringify({ persona, tagging }) }),
  knowledge: () => request<KnowledgeResponse>("/api/knowledge"),
  files: () => request<{ files: string[] }>("/api/files"),
  file: (path: string) => request<{ path: string; content: string }>(`/api/file?path=${encodeURIComponent(path)}`),
  saveFile: (path: string, content: string) =>
    request<{ ok: boolean; last_updated: string }>("/api/file", { method: "POST", body: JSON.stringify({ path, content }) }),
  runState: () => request<{ last_launch: unknown }>("/api/run/state"),
  launch: (mode: string, persona?: string, tagging?: boolean) =>
    request<{ last_launch: unknown }>("/api/run/launch", { method: "POST", body: JSON.stringify({ mode, persona, tagging }) }),
};

