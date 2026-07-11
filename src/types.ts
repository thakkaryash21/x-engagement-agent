export type TabKey = "drafts" | "insights" | "knowledge" | "settings" | "run";

export type DraftRow = Record<string, string>;

export interface DraftItem {
  id: string;
  type: string;
  status?: string;
  row: DraftRow;
  raw: string;
  stale_age: boolean | null;
}

export interface DraftsResponse {
  drafts: DraftItem[];
}

// Mirrors incidents.csv — column set owned by dashboard/tables.py (COLUMNS_INCIDENTS).
// Keep these keys in sync with that spec (10 columns, in header order).
export interface Incident {
  incident_id?: string;
  occurred_at?: string;
  persona?: string;
  mode?: string;
  type?: string;
  description?: string;
  session_action?: string;
  lockout_triggered?: string;
  acknowledged_at?: string;
  notes?: string;
}

export interface IncidentsResponse {
  incidents: Incident[];
  locked_out: boolean;
}

export interface FunnelCounts {
  drafted: number;
  approved: number;
  edited: number;
  discarded: number;
  sent: number;
  reviewed: number;
}

export interface InsightsResponse {
  funnel: {
    replies: FunnelCounts;
    tweets: FunnelCounts;
  };
  edit_rate: {
    sent: number;
    edited: number;
    rate: number | null;
  };
  performance: {
    by_reply_archetype: Record<string, { n: number; avg_engagement_rate: number }>;
    by_content_type: Record<string, { n: number; avg_engagement_rate: number }>;
  };
  profiles: Record<string, string>[];
}

export interface KnowledgeFile {
  path: string;
  content: string;
}

export type KnowledgeResponse = Record<string, KnowledgeFile[]>;

export interface PersonaResponse {
  active: {
    persona: string | null;
    tagging: "on" | "off" | null;
  };
  available: string[];
}

