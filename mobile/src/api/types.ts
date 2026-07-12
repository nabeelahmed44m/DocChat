/** Wire types mirroring the FastAPI backend schemas (app/api/schemas.py). */

export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed';

export interface DocumentRecord {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error: string | null;
  stats: Record<string, number>;
  persist: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentList {
  documents: DocumentRecord[];
  count: number;
}

export interface StatusResponse {
  id: string;
  status: DocumentStatus;
  error: string | null;
  stats: Record<string, number>;
}

export interface AskResponse {
  document_id: string;
  question: string;
  answer: string;
}

export interface SearchAnswer {
  text: string;
  score: number;
  page_number: number;
  char_start: number;
  char_end: number;
  passage_index: number;
  context: string;
  matched_entities: string[];
  citation: string;
}

export interface SearchResultItem {
  document_id: string;
  filename: string;
  answer: SearchAnswer;
}

export interface SearchResponse {
  question: string;
  searched_documents: number;
  results: SearchResultItem[];
}

export interface HealthResponse {
  status: string;
  version: string;
  supported_extensions: string[];
  ocr_available: boolean;
  libreoffice_available?: boolean;
  lsa_enabled?: boolean;
  auth_required?: boolean;
  store_backend?: string;
  multi_document_search?: boolean;
}

export interface SummaryResponse {
  document_id: string;
  summary: string;
  bullet_points: string[];
}

export interface KeyPointsResponse {
  document_id: string;
  points: string[];
  keyphrases: string[];
}

export interface TableData {
  page_number: number;
  header: string[];
  rows: string[][];
  n_rows: number;
  n_cols: number;
  title?: string | null;
}

export interface TablesResponse {
  document_id: string;
  engine: string;
  count: number;
  note: string | null;
  tables: TableData[];
}

/** A local file chosen from the picker/camera, ready to upload. */
export interface PickedFile {
  uri: string;
  name: string;
  mimeType: string;
  size?: number;  // bytes, populated by pickers that expose it
}

export interface BillingStatus {
  plan: 'free' | 'pro';
  status: 'active' | 'inactive' | 'past_due' | 'canceled';
  current_period_end: string | null;
}

export interface CheckoutResponse {
  url: string;
}
