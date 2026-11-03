# Haske Agent Prompt Architecture

This file documents the exact prompts and pipeline logic for each of the
three tiers. It is the single source of truth for what we ask the model to do
and what the deterministic code decides.

The verdict is ALWAYS decided by deterministic code in `api/verdict/engine.py`.
The model never picks a verdict. It only extracts fields and, as a separate
call, writes a short plain-language explanation of a verdict already decided.

---

## Tier 1 - Registry facts (code, no model)

Handled entirely by `api/registries/` and `api/verdict/engine.py`.

Checks (in order of priority):

1. NRN not found, malformed, or is a barcode -> NOT_FOUND / CANNOT_CONFIRM
2. NRN exists but the register shows it belongs to a different product -> REGISTRY_MISMATCH
3. Registration expired or inactive -> EXPIRED_OR_INACTIVE
4. NRN shared by more than one product -> CANNOT_CONFIRM (AMBIGUOUS)
5. Recall in the alert feed matching NRN + batch -> ALERT_MATCH (milestone 2)
6. All clear -> CONSISTENT_WITH_REGISTRY

---

## Tier 2 - Label forensics (Meta Model API vision call)

### 2a. Extraction prompt

Sent as the user message to the vision model. The model returns structured JSON.
It never writes a verdict; it only fills fields and flags legibility issues.

```
EXTRACTION_PROMPT (single user message with the image attached)
```

```
Read the product label in the image. Extract every field in the JSON schema below.
Return ONLY valid JSON, no commentary, no markdown.

Rules you must follow:
1. If a field is not visible or legible, set its value to null and its
   confidence to 0.0. Add a short note to legibility_notes.
2. Dates must use the format YYYY-MM-DD. If a date shows only month and year
   (e.g. "08/2027"), use the last day of that month: "2027-08-31".
3. For nrn, extract the NAFDAC registration number exactly as printed.
   Do not infer or reconstruct it. Common patterns: "A4-100160", "B2-0451".
4. For batch, copy the batch/lot code exactly as printed.
5. Confidence is your reading confidence for each field (0.0 to 1.0).
6. For layout_flags: inspect the label for any of these anomalies and list
   every one you see. An empty list means none observed.

Schema:
{
  "product_name":     "string or null",
  "nrn":              "string or null (the NAFDAC registration number)",
  "batch":            "string or null",
  "manufacture_date": "string or null (YYYY-MM-DD)",
  "expiry_date":      "string or null (YYYY-MM-DD)",
  "manufacturer":     "string or null",
  "strength":         "string or null",
  "category_guess":   "string or null (drug, vaccine, device, veterinary, herbal, food, water, cosmetic, soap)",
  "shelf_life_months": "integer or null (the stated shelf life in months, if printed)",
  "confidence": {
    "product_name": 0.0,
    "nrn": 0.0,
    "batch": 0.0,
    "manufacture_date": 0.0,
    "expiry_date": 0.0,
    "manufacturer": 0.0,
    "strength": 0.0,
    "category_guess": 0.0
  },
  "legibility_notes": ["string"],
  "layout_flags": [
    "SPELLING_ERROR:<word>",
    "DATE_IN_FUTURE:<field>",
    "SHELF_LIFE_INCONSISTENT",
    "BATCH_FORMAT_UNUSUAL:<reason>",
    "FONT_INCONSISTENCY:<location>",
    "RESTICKERED_AREA:<location>",
    "MISSING_SECURITY_ELEMENT:<element>",
    "LOGO_QUALITY_LOW",
    "TEXT_ALIGNMENT_OFF:<location>"
  ]
}
```

### 2b. Consistency checks (deterministic code, no model call)

After extraction, `api/extraction/consistency.py` runs these checks in order.
Each check that fires adds a finding to a new `consistency_flags` list returned
alongside the extraction. These become signals in the verdict evidence, not the
verdict itself.

| Check | Rule | Flag |
|-------|------|------|
| Expiry in past | expiry_date < today | `EXPIRY_PAST` |
| Expiry in far future | expiry_date > today + 10 years | `EXPIRY_FAR_FUTURE` |
| Manufacture in future | manufacture_date > today | `MFG_IN_FUTURE` |
| Shelf life mismatch | shelf_life_months is set AND expiry - mfg date differs by more than 60 days from stated shelf life | `SHELF_LIFE_MISMATCH` |
| Batch format unusual | batch matches `isUnusualBatch` heuristic (all same digit or long sequential run) | `BATCH_PATTERN_UNUSUAL` |
| Layout flags present | any entry in extraction.layout_flags | forwarded as-is |

### 2c. Manufacturer cross-check (deterministic, no model call)

`api/registries/manufacturer_list.py` holds a list of known legitimate NAFDAC
manufacturers. If `extraction.manufacturer` is set and confidence >= 0.5:

- fuzzy match (token_sort_ratio >= 80) against the list
- if no match: add `MANUFACTURER_UNKNOWN` to consistency_flags

This is a signal only. An unknown manufacturer does not by itself change the
verdict; it becomes part of the evidence note.

---

## Tier 3 - Crowdsourced batch conflict (observation ledger)

### Data model

```sql
CREATE TABLE observations (
    id          TEXT PRIMARY KEY,
    nrn         TEXT NOT NULL,
    batch       TEXT NOT NULL,
    mfg_date    TEXT,
    expiry_date TEXT,
    manufacturer TEXT,
    pack_size   TEXT,
    region      TEXT,             -- coarse: state or LGA, opt-in only
    source      TEXT DEFAULT 'user',  -- 'user' | 'seed' | 'synthetic'
    ts          TEXT NOT NULL,    -- ISO 8601
    device_hash TEXT              -- one-way hash of device ID, for rate limiting
);
```

No photos are stored. Only extracted text fields and coarse location.

### Conflict rule (deterministic, no model)

After a new observation is inserted, `api/observations/conflict.py` runs:

```python
# For a given (nrn, batch), all observations with source != 'synthetic'
# should have the same expiry_date and manufacture_date.
# If any stored observation disagrees with the new one by more than 3 days:
#   -> add BATCH_DATE_CONFLICT to consistency_flags
#   -> include count and first-seen date in evidence note
```

Threshold of 3 days accounts for OCR reading errors (e.g. "08/2027" vs "2027-08-31").

### Conflict flag in the verdict

`api/verdict/engine.py` receives consistency_flags as a new parameter.
If `BATCH_DATE_CONFLICT` is present, the evidence note includes:

```
"batch_conflict: expiry differs from N prior observations of this batch (first seen YYYY-MM-DD)"
```

The verdict code does NOT change from CONSISTENT_WITH_REGISTRY to anything worse
based on a conflict alone. Conflicts are evidence signals, not verdicts, because:
- We have a small seed set, not a validated network
- A genuine product could have an OCR-read error in the prior observations
- False accusations carry legal risk

The result screen shows a distinct `BATCH_CONFLICT` evidence row with wording:
"The stated expiry date differs from N other scans of this batch."

### Rate limiting and anti-poisoning

- Per device_hash: max 10 observations per hour, 50 per day
- A (nrn, batch) pair needs at least 5 observations before a conflict flag fires
- Observations with source='synthetic' are counted toward the floor but never
  used as conflict evidence (they set the expected values, not flag departures)
- Observations with source='seed' (from trusted pharmacies/manufacturers) carry 3x weight

---

## Tier 2 - Explanation prompt (separate call, after verdict is decided)

This is the existing `api/extraction/explain.py` LLMExplainer, upgraded to
include consistency_flags and any batch conflict.

```
EXPLANATION_PROMPT (system)
```

```
You are a product-safety assistant for Nigeria.
A deterministic code has already decided the verdict for a NAFDAC product check.
Your only job is to write a clear, calm, 2-to-3 sentence explanation of the
verdict and any signals found, in plain English for a non-expert user.

Rules you must follow:
1. Never write "fake" or "counterfeit". Say "indicators found" or
   "the register shows".
2. Never certify a product as genuine. The best positive result is
   "consistent with the registry, which does not prove authenticity".
3. Never give dosing, take, or stop advice.
4. If category is drug, vaccine, herbal, or device, end with:
   "If you have concerns, ask a pharmacist."
5. If consistency_flags contains layout or date signals, mention them
   briefly and factually (e.g. "The label shows a date inconsistency
   that is worth noting").
6. If there is a batch conflict, state it plainly: "The expiry date on
   this label differs from [N] other scans of the same batch code."
7. Return only the explanation text. No JSON, no markdown, no headers.
```

```
EXPLANATION_PROMPT (user message)
```

```
Verdict code: {verdict_code}
Product: {product_name or "unknown"}
Registration number: {nrn or "unknown"}
Category: {category or "unknown"}
Evidence note: {evidence_note or "none"}
Consistency signals: {json.dumps(consistency_flags) or "none"}
Batch conflict: {batch_conflict_note or "none"}
```

---

## What the Meta Model API is and is not asked to do

| Task | Model call? | Notes |
|------|-------------|-------|
| Extract fields from label photo | Yes (vision) | Tier 2a. Only call with the image. |
| Detect layout flags | Yes (same vision call) | Part of the extraction schema. |
| Decide the verdict | No | Deterministic code only. |
| Run consistency date checks | No | Deterministic code only. |
| Run batch conflict check | No | Deterministic SQL only. |
| Write plain-language explanation | Yes (text) | Tier 2c. Receives only the decided code + signals. |
| Segment label regions (SAM 3.1) | Future work | Not in milestone 1. |

---

## Verdict state machine (complete, post-tier-2)

```
NOT_FOUND_IN_REGISTRY       NRN not in any registry
EXPIRED_OR_INACTIVE         NRN found, registration lapsed
REGISTRY_MISMATCH           NRN found, product name or maker mismatches
CANNOT_CONFIRM              NRN ambiguous, or registry unreachable, or extraction failed
ALERT_MATCH                 NRN + batch matches official recall (milestone 2)
CONSISTENT_WITH_REGISTRY    All registry checks pass
```

Consistency signals and batch conflicts appear in the evidence section of any
of these states. They do not create new verdict codes. The UI renders them as
a separate card with amber coloring ("signals found") underneath the main verdict.

---

## What this is and is not

This system is a "does the label match the register, plus label signals and
known alerts" checker. It is not an authenticity detector.

What it catches:
- NRN not found, malformed, or barcodes
- NRN belongs to a different product
- Registration expired or inactive
- NRN shared (ambiguous)
- Official NAFDAC recall matching NRN + batch (milestone 2)
- Date inconsistencies on the label
- Layout anomalies the vision model can see (spelling errors, font shifts,
  misplaced elements)
- Manufacturer not in known list
- Batch codes that conflict with prior observations

What it cannot prove:
- That a product is genuine
- That the physical content matches the label
- That a label was not copied from a genuine product

The UI always shows: "A match means the label agrees with the registry.
It does not prove the product is genuine."
