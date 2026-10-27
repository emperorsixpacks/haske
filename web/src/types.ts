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

export interface Evidence {
  source: string;
  source_url: string | null;
  retrieved_at: string | null;
  fields_compared: Array<{ field: string; label_value: string | null; registry_value: string | null; similarity: number }>;
  note: string | null;
}

export interface Verdict {
  code: string;
  title: string;
  message: string;
  footer: string | null;
  evidence: Evidence[];
  abstained: boolean;
}

export interface CheckResponse {
  extraction: Extraction;
  nrn: { raw: string | null; canonical: string | null; is_barcode: boolean; valid: boolean };
  match_outcome: string;
  verdict: Verdict;
}
