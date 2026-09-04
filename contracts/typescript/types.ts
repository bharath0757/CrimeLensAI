/**
 * CrimeLensAI — Shared TypeScript Types
 * ========================================
 * Type definitions shared between the React frontend and backend API.
 *
 * These types MUST stay in sync with the Python Pydantic models in
 * /packages/shared-types/python/schemas.py
 *
 * When modifying types here, update the Python counterpart too.
 */

// ============================================================
// Enums
// ============================================================

export enum EntityType {
  PERSON = "PERSON",
  PHONE = "PHONE",
  VEHICLE = "VEHICLE",
  UPI_ID = "UPI_ID",
  LOCATION = "LOCATION",
  ORG = "ORG",
}

export enum UserRole {
  INVESTIGATOR = "INVESTIGATOR",
  SUPERVISOR = "SUPERVISOR",
  ADMIN = "ADMIN",
}

export enum CaseStatus {
  DRAFT = "DRAFT",
  PROCESSING = "PROCESSING",
  ACTIVE = "ACTIVE",
  CLOSED = "CLOSED",
  ARCHIVED = "ARCHIVED",
}

// ============================================================
// Entity Types
// ============================================================

export interface ExtractedEntity {
  id?: string;
  entity_type: EntityType;
  value: string;
  /** Extraction confidence score, 0.0–1.0 */
  confidence: number;
  /** Character start position in source text */
  start_offset: number;
  /** Character end position in source text */
  end_offset: number;
  /** Which input field the entity was found in */
  source_field: string;
  case_id?: string;
  /** null = pending review, true = confirmed, false = rejected */
  confirmed?: boolean | null;
}

export interface EntityResolutionGroup {
  canonical_value: string;
  entity_type: EntityType;
  variants: ExtractedEntity[];
  merge_confidence: number;
}

// ============================================================
// Case Types
// ============================================================

export interface CaseCreate {
  title: string;
  fir_text?: string;
  call_records?: string;
  financial_logs?: string;
  location_data?: string;
  district?: string;
  station?: string;
  filing_date?: string; // ISO 8601
}

export interface CaseResponse {
  id: string;
  title: string;
  status: CaseStatus;
  district?: string;
  station?: string;
  filing_date?: string;
  created_at: string;
  updated_at: string;
  entities: ExtractedEntity[];
  linked_case_count: number;
}

export interface CaseListResponse {
  cases: CaseResponse[];
  total: number;
  skip: number;
  limit: number;
}

// ============================================================
// Graph Types
// ============================================================

export interface GraphRelationship {
  id?: string;
  source_entity_id: string;
  target_entity_id: string;
  relationship_type: string;
  source_case_id: string;
  confidence: number;
  /** Human-readable explanation of why these entities are linked */
  why_linked: string;
}

export interface CrossCaseLink {
  case_a_id: string;
  case_b_id: string;
  shared_entities: ExtractedEntity[];
  link_strength: number;
  explanation: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType | "CASE";
  metadata?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  label: string;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface LinkAlert {
  id: string;
  case_ids: string[];
  shared_entity_ids: string[];
  severity: "LOW" | "MEDIUM" | "HIGH";
  status: "NEW" | "ACKNOWLEDGED";
  title: string;
  explanation: string;
  created_at: string;
}

export interface InvestigativePattern {
  pattern_type:
    | "REPEATED_IDENTIFIER"
    | "MULTI_SIGNAL_CONVERGENCE"
    | "BRIDGE_ENTITY";
  case_ids: string[];
  confidence: number;
  supporting_entity_ids: string[];
  explanation: string;
  disposition: "INVESTIGATIVE_LEAD_NOT_FACT";
}

export interface LinkPrediction {
  source_entity_id: string;
  target_entity_id: string;
  confidence: number;
  common_neighbor_ids: string[];
  method: "jaccard_plus_adamic_adar";
  explanation: string;
  disposition: "INVESTIGATIVE_LEAD_NOT_FACT";
}

// ============================================================
// Ledger Types
// ============================================================

export interface LedgerRecord {
  id?: string;
  timestamp: string;
  action: string;
  actor_id: string;
  resource_type: string;
  resource_id: string;
  data_hash: string;
  previous_hash?: string;
  chain_position: number;
}

export interface LedgerVerification {
  record_id: string;
  verified: boolean;
  computed_hash: string;
  stored_hash: string;
  chain_intact: boolean;
  message: string;
}

// ============================================================
// Auth Types
// ============================================================

export interface UserProfile {
  id: string;
  username: string;
  full_name: string;
  role: UserRole;
  district?: string;
  station?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  token_type: string;
  user: UserProfile;
}

// ============================================================
// Dashboard Types
// ============================================================

export interface DashboardStats {
  total_cases: number;
  total_entities: number;
  cross_case_links: number;
  pending_reviews: number;
  cases_by_status: Record<string, number>;
  recent_links: CrossCaseLink[];
}

// ============================================================
// API Response Wrapper
// ============================================================

export interface ApiResponse<T> {
  status: "ok" | "error";
  data?: T;
  message?: string;
  errors?: string[];
}
