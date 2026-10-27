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
- Full pytest suite passes: 53 tests (NRN, matcher, greenbook, napams, verdict, extraction,
  service, API). `uv run pytest -q` -> 53 passed.- Live server smoke test (uvicorn, real HTTP): `GET /v1/health` -> ok; `GET /v1/registry/status`
  -> source/date/count; `POST /v1/check/fields` returns CONSISTENT_WITH_REGISTRY (with footer +
  evidence), REGISTRY_MISMATCH, NOT_FOUND_IN_REGISTRY as expected; `POST /v1/check` (multipart
  image) in MOCK mode extracts the fixture NRN and returns CONSISTENT_WITH_REGISTRY.
- Eval harness runs now (`uv run python eval/run_eval.py`): 6/6 verdict agreement, 0 false
  accusations, NRN/batch/expiry exact-match 5/6 (the misses are the deliberate null-NRN and
  wrong-batch fixtures).
- Web frontend builds clean: `npm run build` -> 148 kB JS, no type errors.
- NAPAMS verify form is VERIFIED against live HTML (fetched 2026-10-27): a single form on the
  home page (`#verify`) POSTing to `/Home/VerifyProduct`, with input
  `id="CertificateNumber" name="CertificateNumber"`, a `__RequestVerificationToken` hidden
  anti-forgery field, and a submit button guarded by Google reCAPTCHA v3 (invisible,
  `data-callback="onSubmit"`, sitekey `6LcG85gsAAAAALLXn_03izJ7kEsmKS1SCpH5ZVhw`). Automated
  submission is blocked by the captcha, so the client returns CHECK_INCOMPLETE("captcha_protected").
- Greenbook response shape is VERIFIED against the live site (fetched 2026-10-27, `recordsTotal`
  = 8950): it is a Laravel server-side DataTables feed at the site root returning
  `{draw, recordsTotal, recordsFiltered, data, queries, input}` where `data` is an array of
  object rows. Verified row keys: `NAFDAC` (the NRN, e.g. "A4-100160"), `product_name`
  (may carry trailing `##`/`*` that the site strips), `status`, `applicant_name`,
  `ingredient_name`, `strength`, `form_name`, `category_name`, `approval_date`, `expiry_date`,
  `composition`, `pack_size`. The live `probe` command and `normalise()` both succeed on real
  data (e.g. NRN "A4-100160" -> "AG Spironolactone", Active, expiry 2026-12-16).
- Greenbook robots.txt is permissive (`Disallow:` empty), so `fetch` is allowed by policy.

## Not verified (could not reach from this environment)

- The NAPAMS result layout (what a successful verify returns) cannot be observed without
  solving the captcha; `_parse_record` remains a best-effort stub.
- Greenbook `manufacturer`: the search feed exposes only `manufacturer_id`, not a name, so
  the snapshot's `manufacturer` is None. Enriching it would require the `/manufacturers`
  list or per-product `/products/details/{id}` pages (not done in milestone 1).

## Assumptions (NOT verified)

- **Greenbook DataTables endpoint**: verified working (see above). The only remaining
  assumption is that ~8,950 records are complete enough to page fully; a full `fetch` has not
  been run yet (it pages ~18 pages with a 2s delay).
- **NAPAMS form behaviour**: the form is reCAPTCHA-v3 protected (verified, see above), so the
  food/water/veterinary/general lookup path is effectively CHECK_INCOMPLETE("captcha_protected")
  for automated use. A manual/human-assisted path is out of scope for milestone 1.
- **NRN format**: Assumed canonical form is a letter-prefix group + number, e.g. `A4-0123`,
  `04-5808`. Case/space/dash variants normalised. `O` vs `0` ambiguity is flagged, never
  guessed. 12-13 digit strings are treated as barcodes, not NRNs.
- **NRN uniqueness**: NRNs are NOT guaranteed unique; some are shared by several products.
  Modelled as one NRN -> many products, with shared numbers producing AMBIGUOUS.
- **Category routing**: drugs/vaccines/devices/vet/herbals route to Greenbook snapshot;
  food/water/veterinary/general route to NAPAMS; cosmetics/soaps return
  CHECK_INCOMPLETE("no_registry_source").
- **Registry categories**: Verified from the live Greenbook category selector: Drugs,
  Vaccines and Biologics, Medical devices, Veterinary, Herbals and Nutraceuticals, and
  Disinfectants (no cosmetics/soaps). Disinfectants is mapped to DEVICE for routing/footer.
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
- Wire the SAM 3.1 `preprocess` crop (milestone 2) and the public-alert parser (ALERT_MATCH).
- Route the LLM explanation layer through `verdict/safety.is_medical_advice_request`.
