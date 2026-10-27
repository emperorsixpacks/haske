# NOTES.md

Working assumptions and unverified items for Haske (Milestone 1). Keep this file current
as the build proceeds. Andrew reviews this to know what was verified vs assumed.

## Verified (confirmed by running)

- Meta Model API base URL is `https://api.meta.ai/v1` (confirmed against dev.meta.ai docs).
- Meta Model API is OpenAI-compatible at `/v1/chat/completions`; images are sent as base64
  `data:` URLs inside `image_url` content blocks (confirmed against docs).
- Vision-capable hosted model ids: `muse-spark-1.3` (recommended), `muse-spark-1.2`,
  `muse-spark-1.1`, `muse-wonder-1.0`. Default for `META_VISION_MODEL` is `muse-spark-1.3`.
- Local toolchain: Python 3.12.13 available via uv, Node 22, npm 10.

## Assumptions (NOT verified)

- **Greenbook response shape**: The report that greenbook.nafdac.gov.ng loads a DataTables
  JSON feed via a GET to the site root with `X-Requested-With: XMLHttpRequest`, paged by
  `start` and `length` (~9,000 records), is UNVERIFIED. The `probe` command is written to
  fetch 3 rows, print raw fields, and fail loudly if the shape differs. Do not trust the
  column names until `probe` has been run against the live site.
- **NAPAMS form behaviour**: The public "verify a product" forms at
  registration.nafdac.gov.ng are assumed to exist but the DOM/selectors/flow are UNKNOWN.
  The Playwright client is written with placeholder selectors and a hard timeout; it must be
  re-tuned against the live portal. All unknown states return CHECK_INCOMPLETE, never
  NOT_FOUND.
- **NRN format**: Assumed canonical form is a letter-prefix group + number, e.g. `A4-0123`,
  `04-5808`. Case/space/dash variants normalised. `O` vs `0` ambiguity is flagged, never
  guessed. 12-13 digit strings are treated as barcodes, not NRNs.
- **NRN uniqueness**: NRNs are NOT guaranteed unique; some are shared by several products.
  Modelled as one NRN -> many products, with shared numbers producing AMBIGUOUS.
- **Category routing**: drugs/vaccines/devices/vet/herbals route to Greenbook snapshot;
  food/water/veterinary/general route to NAPAMS; cosmetics/soaps return
  CHECK_INCOMPLETE("no_registry_source").
- **Registry categories**: The exact set of Greenbook categories and their names is unknown
  until `probe` runs. The normaliser maps the common ones and stores everything else verbatim.
- **Playwright availability**: NAPAMS lookups require a Playwright browser install
  (`playwright install chromium`). Tests use a fixture-backed fake and never launch a browser.

## Deliberate product decisions (assumptions)

- Verdicts are decided by deterministic code only. The LLM extracts fields and writes plain
  language explanations of a verdict code already decided by the engine.
- The best possible positive result is "consistent with the registry, which does not prove
  authenticity". We never certify a product as genuine and never say "fake"/"counterfeit"
  unless a cited official alert matches product AND batch (milestone 2).
- Medicines append a fixed footer: ask a pharmacist, report suspicions to NAFDAC. The system
  gives no dosing or take/stop advice.
- User photos are never persisted. Logs carry non-identifying metrics only.

## Open questions / TODOs

- Run `probe` against the live Greenbook site and adapt `greenbook.py` column mapping.
- Re-tune NAPAMS Playwright selectors against the live portal.
- Add real photos + labels.csv rows (Andrew to supply 20).
