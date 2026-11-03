# eval/photos

This directory holds extraction fixture files for the eval harness.

## Status

Real product photos are pending (Andrew to supply ~20). The current `.json` files are
synthetic fixtures written by hand to exercise the eval harness logic.

## Format

Each file is named `<image_filename>.json` where `<image_filename>` matches the `image`
column in `eval/labels.csv`. The JSON must match the `ExtractionResult` schema:

```json
{
  "product_name": "Paracetamol Tablets 500mg",
  "nrn": "A4-0123",
  "batch": "BN2024001",
  "manufacture_date": "2024-01-15",
  "expiry_date": "2026-01-14",
  "manufacturer": "Acme Pharma Ltd",
  "strength": "500mg",
  "category_guess": "drug",
  "confidence": {
    "product_name": 0.97,
    "nrn": 0.99,
    "batch": 0.95,
    "manufacture_date": 0.90,
    "expiry_date": 0.92,
    "manufacturer": 0.88,
    "strength": 0.96,
    "category_guess": 0.99
  },
  "legibility_notes": []
}
```

Null any field that was not legible on the label and set its confidence to `0.0`.

## Adding a real photo

1. Place the image in `eval/photos/` (e.g. `photo_007.jpg`).
2. Run `uv run python -m api.cli smoke` to confirm vision extraction works.
3. Run the vision extractor against the image and save the output JSON as
   `eval/photos/photo_007.jpg.json`.
4. Add a row to `eval/labels.csv` with the true values for that image.
5. Run `uv run python eval/run_eval.py` to check the new row is included.

## Eval labels.csv columns

- `image`: filename (e.g. `photo_007.jpg`)
- `true_nrn`: canonical NRN (e.g. `A4-0123`)
- `true_batch`: batch number or empty
- `true_expiry`: expiry date `YYYY-MM-DD` or empty
- `expected_verdict`: one of `CONSISTENT_WITH_REGISTRY`, `REGISTRY_MISMATCH`,
  `NOT_FOUND_IN_REGISTRY`, `EXPIRED_OR_INACTIVE`, `CANNOT_CONFIRM`
