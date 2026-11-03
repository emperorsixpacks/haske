export interface FieldConfidence {
  product_name: number;
  nrn: number;
  batch: number;
  manufacture_date: number;
  expiry_date: number;
  manufacturer: number;
  strength: number;
  category_guess: number;
}

export interface Extraction {
  product_name: string | null;
  nrn: string | null;
  batch: string | null;
  manufacture_date: string | null;
  expiry_date: string | null;
  manufacturer: string | null;
  strength: string | null;
  category_guess: string | null;
  confidence: FieldConfidence;
  legibility_notes: string[];
}

export interface FieldComparison {
  field: string;
  label_value: string | null;
  registry_value: string | null;
  similarity: number;
}

export interface Evidence {
  source: string;
  source_url: string | null;
  retrieved_at: string | null;
  fields_compared: FieldComparison[];
  note: string | null;
}

export type VerdictCode =
  | "CONSISTENT_WITH_REGISTRY"
  | "REGISTRY_MISMATCH"
  | "NOT_FOUND_IN_REGISTRY"
  | "EXPIRED_OR_INACTIVE"
  | "ALERT_MATCH"
  | "CANNOT_CONFIRM";

export interface Verdict {
  code: VerdictCode;
  title: string;
  message: string;
  explanation: string | null;
  footer: string | null;
  evidence: Evidence[];
  abstained: boolean;
}

export interface NrnInfo {
  raw: string | null;
  canonical: string | null;
  is_barcode: boolean;
  ambiguous_o_zero: boolean;
  error: string | null;
  valid: boolean;
}

export interface CheckResponse {
  extraction: Extraction;
  nrn: NrnInfo;
  match_outcome: string;
  verdict: Verdict;
}

export interface RegistryStatus {
  source: string;
  snapshot_date: string | null;
  record_count: number;
}

/* Local types (device-only, never sent to the server). */

export type PhotoRole = "front" | "back" | "batch";

export interface CapturedPhoto {
  id: string;
  role: PhotoRole;
  dataUrl: string;
  bytes: number;
}

export type CheckInput =
  | { kind: "image"; photos: CapturedPhoto[] }
  | { kind: "fields"; nrn: string; product_name: string };

export type CheckOutcome =
  | { kind: "ok"; response: CheckResponse }
  | { kind: "error"; reason: "network" | "timeout" | "server" | "http"; status?: number; detail?: string };

export interface SavedResult {
  id: string;
  savedAt: string;
  outcome: CheckResponse;
  keepPhotos: boolean;
  photos: CapturedPhoto[];
}

export type VerdictTone = "match" | "differ" | "notfound" | "unreadable";
