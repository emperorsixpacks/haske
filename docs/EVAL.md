# EVAL.md

Honest evaluation of the Haske investigator. Everything here runs; nothing is fabricated.
Numbers that need the 20-30 real label photos (Andrew to supply) are marked "not measured yet".

## What is measured now (runs without real photos)

`uv run python eval/run_investigator_eval.py` replays the real NAFDAC alert fixtures through
the deterministic pipeline:

| Metric | Result |
|--------|--------|
| Alerts loaded | 2 (Postinor-2 027/2025, BPPL Artemether/Lumefantrine 042/2026) |
| Alert-replay recall | 3/3 (100%) |
| False-positive rate on genuine fixtures | 0/3 (0%) |
| KNOWN_TARGET detection (unlisted batch) | 1/1 |
| Cost per deterministic check | 0 model tokens, 0 vision calls |

The replay covers: both Postinor-2 counterfeit batches and the BPPL falsified batch return
`ALERT_MATCH`; the Postinor-2 genuine batch and an unrelated genuine drug return
`CONSISTENT_WITH_REGISTRY`; a Postinor-2 batch not in the alert returns `KNOWN_TARGET`.

## Live agent observations (real muse-spark-1.3, real Postinor-2 photo)

Verified end to end, not a benchmark:

- Function calling works: the agent runs the tool loop (read_label, registry_lookup,
  alert_search, sanity_checks, reread_region, compare_to_alert, visual_check, mas_guide).
- The alert corpus in the system prompt surfaces a candidate, and code verifies it.
- The targeted visual check correctly answered that the label spells "Veify" instead of
  "Verify" (confidence 0.9) on the injected misspelling.
- Reasoning effort correctly bumps low to high when an alert candidate appears.

## Known failure examples (do not hide these)

1. **The agent does not always call `finish`.** On the live run it kept investigating until
   the 45s budget expired, so `outcome` was `budget_exceeded` and the report was empty. The
   deterministic fallback still returned the correct `ALERT_MATCH`. Fix: a stronger
   finish nudge and a cheaper `reread_region` (see next point).
2. **`reread_region` was slow before boxes landed** (26s for a full-image re-read). After the
   two-pass crop work it crops the region first; the re-read cost needs re-measuring.
3. **`visual_check` returned `None` content** at `max_tokens=400` because the reasoning model
   spent the budget on reasoning tokens. Fixed by raising to 900 and guarding null content.

## Not measured yet (blocked on data)

- **Field accuracy** (NRN/batch/expiry exact-match on real photos): needs the 20-30 photos.
- **Two-read agreement rate** on real labels: the metric exists in
  `api/extraction/two_pass.py`; it has no real photo corpus to run over yet.
- **When does thinking harder help?** (accuracy vs cost at low vs high reasoning effort): the
  effort knob and token counter are wired; producing the chart needs real photos to give an
  accuracy axis. The cost axis is already measurable (reasoning tokens per round).

## Cost controls in place

- Deterministic fast path is the default (0 model tokens per check).
- The agent only fires on a trigger (alert candidate or label signal) and is gated by
  `INVESTIGATOR_ENABLED`.
- Per-run budget: 8 rounds, 45 seconds, and `INVESTIGATOR_TOKEN_CAP` (default 6000) completion
  tokens. Prompt caching makes the static alert corpus cheap across rounds.
