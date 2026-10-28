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
- Web: Vite + React + TypeScript + Tailwind, mobile-first, one page.
- Models: Meta Model API (OpenAI-compatible). Base URL and model ids come from env vars, never
  hardcoded. With no `META_API_KEY` set, Haske runs in MOCK mode using fixtures end to end.

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
