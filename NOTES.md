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
- Full pytest suite passes: 142 tests (NRN, matcher, greenbook, napams, verdict, extraction,
  service, API, alerts, agent, two-pass, cross-view). `uv run pytest -q` -> 142 passed.
- Live server smoke test (uvicorn, real HTTP): `GET /v1/health` -> ok; `GET /v1/registry/status`
  -> source/date/count; `POST /v1/check/fields` returns CONSISTENT_WITH_REGISTRY (with footer +
  evidence), REGISTRY_MISMATCH, NOT_FOUND_IN_REGISTRY as expected; `POST /v1/check` (multipart
  image) in MOCK mode extracts the fixture NRN and returns CONSISTENT_WITH_REGISTRY.
- Eval harness runs now (`uv run python eval/run_eval.py`): 6/6 verdict agreement, 0 false
  accusations, NRN/batch/expiry exact-match 5/6 (the misses are the deliberate null-NRN and
  wrong-batch fixtures).
- Web frontend builds clean: `npm run build` -> 62 kB gzipped JS, no type errors, copy lint
  passes. Rebuilt as a camera-first, phone-only PWA (plain CSS tokens, no Tailwind) with
  self-hosted Inter, manifest + service worker + icons, bottom tabs, an EN/Pidgin string
  dictionary (`web/src/i18n.ts`), and verdict presentation mapped from the deterministic
  `verdict.code` in `web/src/lib/verdict.ts`. The copy lint fails the build on
  "fake"/"counterfeit"/"genuine" outside `src/i18n.ts`.
- NAPAMS verify form is VERIFIED against live HTML (fetched 2026-10-27): a single form on the
  home page (`#verify`) POSTing to `/Home/VerifyProduct`, with input
  `id="CertificateNumber" name="CertificateNumber"`, a `__RequestVerificationToken` hidden
  anti-forgery field, and a submit button guarded by an invisible Google reCAPTCHA
  (`data-callback="onSubmit"`, sitekey `6LcG85gsAAAAALLXn_03izJ7kEsmKS1SCpH5ZVhw`).
- NAPAMS verify RESPONSE is VERIFIED (real response supplied by Andrew, 2026-10-27): a success
  page carries labeled fields "Product Name", "Product Category", "Product Source",
  "Manufacturer", "Date Approved", "Expiry Date", "NAFDAC No", "Active Ingredient", prefixed
  by "Success, Product found". Notably the product name repeats a trailing "(NN-NNNN)" many
  times (a page bug the parser strips). NAPAMS returns COSMETICS too (e.g. Nivea roll-on,
  "02-4139", category "Cosmetics"), so cosmetics/soaps route to NAPAMS, not no_registry_source.
- Greenbook response shape is VERIFIED against the live site (fetched 2026-10-27, `recordsTotal`
  = 8950): it is a Laravel server-side DataTables feed at the site root returning
  `{draw, recordsTotal, recordsFiltered, data, queries, input}` where `data` is an array of
  object rows. Verified row keys: `NAFDAC` (the NRN, e.g. "A4-100160"), `product_name`
  (may carry trailing `##`/`*` that the site strips), `status`, `applicant_name`,
  `ingredient_name`, `strength`, `form_name`, `category_name`, `approval_date`, `expiry_date`,
  `composition`, `pack_size`. The live `probe` command and `normalise()` both succeed on real
  data (e.g. NRN "A4-100160" -> "AG Spironolactone", Active, expiry 2026-12-16).
- Greenbook robots.txt is permissive (`Disallow:` empty), so `fetch` is allowed by policy.
- Meta `muse-spark-1.3` accepts OpenAI-style function/tool calling (verified live), accepts
  `reasoning_effort` (low/high), and benefits from prompt caching (`cached_tokens` observed).
  It does NOT accept video input: a `video_url` content part returns
  `400 invalid_request_error`, so video capture stays out of scope.
- Public-alert DB (`api/registries/alerts.py` + `alert_seed.json`) is live with two real
  NAFDAC alerts curated from nafdac.gov.ng: Postinor-2 `027/2025` (NRN `04-6985`, genuine
  `T32458H`, counterfeits `T36184B`/`332`, known diffs "Veify"/"Distnibuted") and BPPL
  Artemether/Lumefantrine `042/2026` (fake NRN `02-3457`, batch `BP5203`). Matching uses
  O/0 I/1 confusable normalization + Levenshtein edit-1; `verify_alert` confirms a proposed
  alert id. `ALERT_MATCH` and `KNOWN_TARGET` verdicts fire from this seed only.
- Investigator agent (`api/agent/`) runs live: 9 tools, parallel tool execution, 8-round /
  45s / token-cap budget, reasoning effort low→high on alert candidate, trace returned as
  `agent_trace`. `POST /v1/investigate` runs it explicitly. Graceful termination: a plain
  `stop` with content is accepted as the report; a round-3 nudge asks the model to finish.
  The finish report is language-guarded (`api/agent/validator.py` strips
  fake/counterfeit/genuine/authentic/certified plus any URL/NRN/alert number the tools did
  not return), and `CheckService.check_image` wraps escalation in try/except so an agent
  failure can never block or break the deterministic verdict.
- Two-pass reading (`api/extraction/crop.py`, `two_pass.py`): pass 1 returns text + boxes,
  pass 2 re-reads cropped regions and reports an agreement metric (`CROSS_PASS_MISMATCH`
  when they disagree). `reread_region` (agent tool) crops by pass-1 box.
- Targeted visual check (`api/extraction/visual_check.py`) verified live: asked yes/no about
  the "Veify" misspelling, answered yes with confidence 0.9.
- Cross-view check (`api/extraction/cross_view.py`) compares fields across multiple photos.
- Investigator eval (`uv run python eval/run_investigator_eval.py`): 100% alert-replay
  recall, 0% false-positive, 0 deterministic tokens. Numbers live in `docs/EVAL.md`.
- NAFDAC report contact verified from a public alert page: `0800-162-3322`,
  `sf.alert@nafdac.gov.ng` (in `api/app/config.py`). MAS SMS short codes are in config but
  still marked "verify before shipping".

## Not verified (could not reach from this environment)

- NAPAMS automated submission end-to-end was TESTED live (headless Chromium, 2026-10-27):
  the form fills and the Verify button is clicked, but Google reCAPTCHA silently blocks the
  headless/datacenter IP (no token issued, no navigation, no challenge). The client reports
  CHECK_INCOMPLETE("recaptcha_blocked"). On a real residential browser reCAPTCHA auto-passes
  (that is how Andrew captured the Nivea response), so this path would work if the lookup ran
  from a residential IP or a real browser context. Proxy support is now wired:
  `NAPAMS_PROXY_URL` / `NAPAMS_PROXY_USERNAME` / `NAPAMS_PROXY_PASSWORD` in `.env` are passed
  to Playwright's `chromium.launch(proxy=...)` (`http://host:port`, `http://user:pass@host:port`
  or `socks5://host:port`). A residential/mobile proxy on that IP is the intended bypass; still
  untested end to end against the live portal.
- Greenbook `manufacturer`: the search feed exposes only `manufacturer_id`, not a name, so
  the snapshot's `manufacturer` is None. Enriching it would require the `/manufacturers`
  list or per-product `/products/details/{id}` pages (not done in milestone 1).
- Web UI is not covered by automated browser tests yet: the spec'd Playwright (360x800 and
  412x915, throttled network) and Lighthouse (perf/accessibility/PWA > 90) runs need a
  Playwright browser install and are not wired up.

## Assumptions (NOT verified)

- **Greenbook DataTables endpoint**: verified working (see above). The only remaining
  assumption is that ~8,950 records are complete enough to page fully; a full `fetch` has not
  been run yet (it pages ~18 pages with a 2s delay).
- **NAPAMS form behaviour**: the form is guarded by an invisible reCAPTCHA (verified, see
  above). Automated submission may auto-pass or raise a challenge; a challenge is
  CHECK_INCOMPLETE("captcha_challenge"), never NOT_FOUND. Not yet exercised live.
- **NRN format**: Assumed canonical form is a letter-prefix group + number, e.g. `A4-0123`,
  `04-5808`. Case/space/dash variants normalised. `O` vs `0` ambiguity is flagged, never
  guessed. 12-13 digit strings are treated as barcodes, not NRNs.
- **NRN uniqueness**: NRNs are NOT guaranteed unique; some are shared by several products.
  Modelled as one NRN -> many products, with shared numbers producing AMBIGUOUS.
- **Category routing**: drugs/vaccines/devices/vet/herbals route to Greenbook snapshot;
  food/water/veterinary/general/cosmetics/soaps route to NAPAMS (cosmetics/soaps were
  confirmed to work on NAPAMS via a real verify response).
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
  unless a cited official alert matches product AND batch (`ALERT_MATCH` /
  `KNOWN_TARGET`, live from `alert_seed.json`).
- Medicines append a fixed footer: ask a pharmacist, report suspicions to NAFDAC. The system
  gives no dosing or take/stop advice.
- User photos are never persisted. Logs carry non-identifying metrics only.

## Open questions / TODOs

- Run `probe` against the live Greenbook site and adapt `greenbook.py` column mapping.
- Re-tune NAPAMS Playwright selectors against the live portal.
- Add real photos + labels.csv rows (Andrew to supply 20).
- Grow `alert_seed.json` from the 2 live alerts to the 15-alert target (data entry, not code).
- Wire the SAM 3.1 `preprocess` crop (still a stub) for label-region cropping.
- Route the LLM explanation layer through `verdict/safety.is_medical_advice_request`.
- Web: add a real alerts/recalls feed and a claims-check source. The Alerts and Claims tabs are
  honest empty states until a backend source exists (`[BACKEND]` items). Batch-code anomaly is a
  clearly-labelled client heuristic in `web/src/lib/batch.ts`, not a verdict input.
- Web: register a Web Share Target for text so Android Chrome users can share from WhatsApp into
  the Claims tab (not wired yet).
- Web: add the Playwright + Lighthouse test suite (see "Not verified" above).
