# Haske

An AI product-authenticity checker for Nigeria. A user photographs a product; Haske extracts
the label fields, cross-checks the NAFDAC registration number (NRN) against official public
registries, and returns an evidence-backed verdict with citations.

Core principle: verdicts come from deterministic code and cited official sources, never from
the LLM. The LLM only extracts fields and writes plain-language explanations of a verdict code
already decided.

Built for the Meta Global AI Developer Hackathon.

## Stack

- Backend: Python 3.12, FastAPI, uv, SQLite (Postgres-compatible SQL), pytest, httpx.
- Web: Vite + React + TypeScript, mobile-only PWA (camera first). Plain CSS design tokens, no
  Tailwind. Manifest + service worker for installability and offline shell.
- Models: Meta Model API (OpenAI-compatible). Base URL and model ids come from env vars, never
  hardcoded. With no `META_API_KEY` set, Haske runs in MOCK mode using fixtures end to end.

### Which model does what

A single configurable Meta model (`META_VISION_MODEL`, default `muse-spark-1.3`) performs both
model-backed steps, and it never chooses a verdict:

1. **Label extraction** (vision): reads the product photo and returns the structured fields
   (`product_name`, `nrn`, `batch`, dates, `manufacturer`, `strength`, `category_guess`) plus
   per-field confidence. See `api/extraction/vision.py`.
2. **Verdict explanation** (text): writes a plain-language, one-to-two-sentence expansion of a
   verdict code that deterministic code in `api/verdict/engine.py` has already decided. See
   `api/extraction/explain.py`.

Every verdict is decided by deterministic code, never by a model.

### Where Meta's models do the work

The investigator agent (`api/agent/`) is an optional escalation layer (disabled by default;
set `INVESTIGATOR_ENABLED=1`). The deterministic pipeline stays the fast path, and the agent
only fires on a trigger such as an alert candidate or a label signal. It uses these Meta Model
API capabilities, all against the same OpenAI-compatible endpoint:

| Capability | Where it is used |
|------------|------------------|
| Function / tool calling | `api/agent/loop.py` runs the model with `tools` and executes its `tool_calls` |
| Parallel tool calls | multiple tool calls in one round run concurrently (`ThreadPoolExecutor`) |
| Multimodal reads | `read_label`, `reread_region`, and `visual_check` send the label image |
| Two-pass reading | pass 1 reads the whole pack with boxes, pass 2 re-reads cropped NRN/batch/dates |
| Long context | the compact NAFDAC alert corpus is sent in the system prompt; prompt caching makes it cheap across rounds |
| Reasoning effort | low by default, raised to high when two reads disagree or an alert candidate appears |
| Structured output | every tool result is JSON with a schema; the finish report is validated and sanitized by code |
| Bounding boxes | the vision model returns normalized boxes, used to crop regions for re-reads and evidence |

Tool results are the only source of NRNs, URLs, alert text, and registry data. The model drafts
the explanation and next steps; code decides every verdict code and strips any fact the tools
did not return.

## Quick start

```bash
# Backend (MOCK mode, no model key required)
uv sync
uv run uvicorn api.app.main:app --reload

# CLI: probe the Greenbook site, then fetch a full snapshot
uv run python -m api.cli probe
uv run python -m api.cli fetch

# Web (from /web)
npm install
npm run dev
npm run build   # typecheck (tsc) + copy lint + vite build

# Eval harness
uv run python eval/run_eval.py
```

## Environment

Copy `.env.example` to `.env`. `META_API_BASE_URL`, `META_API_KEY`, and `META_VISION_MODEL`
configure the model. Leave `META_API_KEY` empty for MOCK mode.

## API

- `POST /v1/check` (multipart image) -> extraction + match + verdict + evidence.
- `POST /v1/check/fields` (JSON fields, no image) -> same, for testing without the model.
- `GET /v1/health`
- `GET /v1/registry/status` -> snapshot date and record count.

## CLI

- `uv run python -m api.cli probe` fetches 3 Greenbook rows and prints the raw fields. It fails
  loudly if the response shape differs from what is expected.
- `uv run python -m api.cli fetch` pages the full Greenbook table into a dated snapshot with a
  content hash, honouring robots.txt and a 2 second inter-request delay.
- `uv run python -m api.cli verify <NRN> [--category <name>]` looks the number up on the NAPAMS
  portal via Playwright and prints the result. Requires `uv run playwright install chromium`.
  NAPAMS is reCAPTCHA-guarded, so from a datacenter/headless IP this returns
  `recaptcha_blocked`; from a residential IP it auto-passes and returns the record.

See `NOTES.md` for assumptions and unverified items.
