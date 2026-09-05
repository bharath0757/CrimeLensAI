export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: "ADMIN" | "INVESTIGATOR" | "ANALYST";
  is_active: boolean;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface CaseRecord {
  id: string;
  case_number: string;
  title: string;
  description: string;
  status: string;
  entity_count: number;
  document_count: number;
}

export interface CaseInput {
  title: string;
  description: string;
  case_number?: string;
  priority?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  tags?: string[];
}

export interface LinkedCase {
  case_id: string;
  shared_entities: {
    entity_id: string | null;
    entity_type: string;
    value: string;
    canonical_value: string | null;
    confidence: number | null;
  }[];
  link_strength: number;
  explanation: string;
}

export interface CaseLinkageResponse {
  case_id: string;
  linked_cases: LinkedCase[];
  source: string;
}

export interface ExtractionMention {
  entity_id: string;
  entity_type: string;
  value: string;
  normalized_value: string;
  confidence: number;
  start_offset: number;
  end_offset: number;
  source_field: string;
}

export interface ExtractionPreview {
  text: string;
  model: string;
  warnings: string[];
  entities: ExtractionMention[];
  document_sha256: string | null;
}

export interface EvidenceDocument {
  id: string;
  case_id: string;
  original_filename: string;
  processing_status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  extracted_entity_count: number;
  error_message: string | null;
}

export interface ProcessResult {
  success: boolean;
  document_id: string;
  case_id: string;
  message: string;
}
export interface DashboardMetrics {
  total_cases: number;
  high_risk_cases: number;
  linked_networks: number;
  money_flow: string | null;
  active_investigations: number;
  total_entities: number;
  total_relationships: number;
  pending_reviews: number;
  currency: "INR";
}

export interface DashboardOverview {
  generated_at: string;
  data_backend: "postgres" | "memory";
  metrics: DashboardMetrics;
  statistics: {
    cases_by_status: Record<string, number>;
    cases_by_priority: Record<string, number>;
    entities_by_type: Record<string, number>;
    transaction_timeline: { date: string; amount: string; count: number }[];
  };
}

export interface ConnectionAlert {
  id: string;
  case_ids: string[];
  severity: "LOW" | "MEDIUM" | "HIGH";
  status: "NEW" | "ACKNOWLEDGED";
  title: string;
  explanation: string;
  created_at: string;
}

export interface ConnectionAlertPage {
  total: number;
  unread: number;
  items: ConnectionAlert[];
}

export interface IngestionReceipt {
  id: string;
  case_id: string;
  document_id: string;
  kind: "cdr" | "transactions";
  source_sha256: string;
  record_count: number;
  inserted_records: number;
  duplicate_records: number;
  status: "PENDING" | "COMPLETED";
  graph_cursor: number;
  graph_total: number;
  created_at: string;
  completed_at: string | null;
  last_error: string | null;
}
