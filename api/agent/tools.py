"""Tool definitions and handlers for the Haske investigator agent.

Handlers are deterministic code, or thin wrappers over the vision extractor. They are the
only source of facts. Each handler that returns a URL, NRN, batch, or alert number records
it in the context's allowed-facts set so the finish validator can strip anything the tools
did not actually return.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from ..registries.models import RegistryCategory


@dataclass
class AllowedFacts:
    urls: set[str] = field(default_factory=set)
    nrns: set[str] = field(default_factory=set)
    batches: set[str] = field(default_factory=set)
    alert_nos: set[str] = field(default_factory=set)


@dataclass
class AgentContext:
    settings: Any
    extractor: Any
    router: Any
    alert_registry: Any
    images: list[dict]  # {id, data_url}
    extraction: Any | None = None
    nrn: Any | None = None
    category: RegistryCategory = RegistryCategory.UNKNOWN
    consistency_flags: list[str] = field(default_factory=list)
    allowed: AllowedFacts = field(default_factory=AllowedFacts)
    effort_state: dict = field(default_factory=lambda: {"alert_candidate": False, "read_disagreement": False})
    reads: list[dict] = field(default_factory=list)
    boxes: dict = field(default_factory=dict)


def _decode_data_url(data_url: str) -> bytes:
    if "," not in data_url:
        return base64.b64decode(data_url)
    return base64.b64decode(data_url.split(",", 1)[1])


def _extraction_to_dict(ext) -> dict:
    if ext is None:
        return {}
    d = ext.model_dump() if hasattr(ext, "model_dump") else dict(ext)
    # Confidence and legibility notes are the interesting parts for the agent.
    return {
        "product_name": d.get("product_name"),
        "nrn": d.get("nrn"),
        "batch": d.get("batch"),
        "manufacture_date": d.get("manufacture_date"),
        "expiry_date": d.get("expiry_date"),
        "manufacturer": d.get("manufacturer"),
        "strength": d.get("strength"),
        "category_guess": d.get("category_guess"),
        "confidence": d.get("confidence"),
        "legibility_notes": d.get("legibility_notes"),
        "boxes": d.get("boxes"),
    }


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _read_label(args: dict, ctx: AgentContext) -> dict:
    focus = args.get("focus")
    image_id = (args.get("images") or [None])[0]
    image = next((i for i in ctx.images if i["id"] == image_id), None) or (ctx.images[0] if ctx.images else None)

    if image is not None and ctx.extraction is None:
        ext = ctx.extractor.extract(_decode_data_url(image["data_url"]), filename=image.get("id"))
    else:
        ext = ctx.extraction

    result = _extraction_to_dict(ext)
    result["focus"] = focus
    if result.get("nrn"):
        ctx.allowed.nrns.add(str(result["nrn"]))
    if result.get("batch"):
        ctx.allowed.batches.add(str(result["batch"]))
    if ext is not None and getattr(ext, "boxes", None):
        ctx.boxes = dict(getattr(ext, "boxes"))
    ctx.reads.append(result)
    return result


def _reread_region(args: dict, ctx: AgentContext) -> dict:
    field = args.get("field")
    image_id = args.get("image_id")
    image = next((i for i in ctx.images if i["id"] == image_id), None) or (ctx.images[0] if ctx.images else None)

    if image is not None and ctx.extractor is not None:
        box = (ctx.boxes or {}).get(field)
        if box:
            from ..extraction.crop import crop_to_box
            cropped = crop_to_box(_decode_data_url(image["data_url"]), box)
            ext = ctx.extractor.extract(cropped, filename=f"{field}_crop")
        else:
            ext = ctx.extractor.extract(_decode_data_url(image["data_url"]), filename=image.get("id"))
    else:
        ext = ctx.extraction

    d = _extraction_to_dict(ext)
    value = d.get(field)
    if value and field == "nrn":
        ctx.allowed.nrns.add(str(value))
    if value and field == "batch":
        ctx.allowed.batches.add(str(value))

    # Detect disagreement with an earlier read of the same field.
    prior = next((r.get(field) for r in ctx.reads if r.get(field)), None)
    if prior is not None and value is not None:
        from ..extraction.two_pass import field_agreement
        agreement, _ = field_agreement(prior, value)
        if agreement < 0.6:
            ctx.effort_state["read_disagreement"] = True

    ctx.reads.append({"field": field, "value": value, "reread": True})
    return {"field": field, "value": value, "confidence": d.get("confidence", {}).get(field)}


def _registry_lookup(args: dict, ctx: AgentContext) -> dict:
    nrn = str(args.get("nrn") or "")
    category = args.get("category") or ctx.category.value
    ctx.allowed.nrns.add(nrn)
    result = ctx.router.lookup(nrn, _category_from(category))
    records = []
    for r in result.records:
        records.append({
            "nrn": r.nrn,
            "product_name": r.product_name,
            "status": r.status,
            "source": r.source,
            "source_url": r.source_url,
        })
        if r.source_url:
            ctx.allowed.urls.add(r.source_url)
    return {
        "outcome": result.outcome.value if hasattr(result.outcome, "value") else str(result.outcome),
        "reason": result.reason,
        "records": records,
    }


def _alert_search(args: dict, ctx: AgentContext) -> dict:
    nrn = args.get("nrn")
    batch = args.get("batch")
    product = args.get("product")
    finding = ctx.alert_registry.lookup(nrn, batch)
    candidates = []
    if finding is not None:
        a = finding.alert
        if a.alert_no:
            ctx.allowed.alert_nos.add(a.alert_no)
        if a.nrn:
            ctx.allowed.nrns.add(a.nrn)
        if a.source_url:
            ctx.allowed.urls.add(a.source_url)
        candidates.append({
            "alert_id": a.id,
            "alert_no": a.alert_no,
            "product": a.product,
            "nrn": a.nrn,
            "source_url": a.source_url,
            "known_differences": list(a.known_differences),
            "kind": finding.kind,
            "matched_batch": finding.matched.batch if finding.matched else None,
        })
        ctx.effort_state["alert_candidate"] = True
    return {"matched": finding is not None, "candidates": candidates, "product_hint": product}


def _compare_to_alert(args: dict, ctx: AgentContext) -> dict:
    alert_id = args.get("alert_id")
    # Find the alert by id across the registry's records.
    alert = None
    for a in ctx.alert_registry._records:
        if a.id == alert_id:
            alert = a
            break
    if alert is None:
        return {"error": "unknown_alert", "alert_id": alert_id}
    if alert.alert_no:
        ctx.allowed.alert_nos.add(alert.alert_no)
    if alert.source_url:
        ctx.allowed.urls.add(alert.source_url)
    return {
        "alert_id": alert.id,
        "alert_no": alert.alert_no,
        "source_url": alert.source_url,
        "known_differences": list(alert.known_differences),
        "quoted_text": alert.quoted_text,
    }


def _sanity_checks(args: dict, ctx: AgentContext) -> dict:
    return {"flags": list(ctx.consistency_flags)}


def _mas_guide(args: dict, ctx: AgentContext) -> dict:
    provider = (args.get("provider") or "").lower()
    codes = getattr(ctx.settings, "mas_short_codes", {}) or {}
    short_code = codes.get(provider)
    if not short_code:
        return {"provider": provider, "available": False, "known": sorted(codes.keys())}
    return {"provider": provider, "short_code": short_code, "available": True}


def _ask_user(args: dict, ctx: AgentContext) -> dict:
    return {"status": "needs_user", "question": args.get("question"), "kind": args.get("kind")}


def _finish(args: dict, ctx: AgentContext) -> dict:
    return {"status": "finished", "report": args.get("report")}


def _category_from(name: str | None) -> RegistryCategory:
    try:
        return RegistryCategory(name or "unknown")
    except ValueError:
        return RegistryCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict, AgentContext], dict]


TOOLS: list[Tool] = [
    Tool(
        name="read_label",
        description="Read the product label image and return extracted fields with per-field confidence.",
        parameters={"type": "object", "properties": {
            "images": {"type": "array", "items": {"type": "string"}},
            "focus": {"type": ["string", "null"]},
        }, "required": ["images"]},
        handler=_read_label,
    ),
    Tool(
        name="reread_region",
        description="Re-read a single field from the label at higher fidelity to confirm it.",
        parameters={"type": "object", "properties": {
            "image_id": {"type": "string"},
            "field": {"type": "string", "enum": ["nrn", "batch", "manufacture_date", "expiry_date", "product_name", "manufacturer", "strength"]},
        }, "required": ["field"]},
        handler=_reread_region,
    ),
    Tool(
        name="registry_lookup",
        description="Look up a NAFDAC registration number in the Greenbook and NAPAMS registries.",
        parameters={"type": "object", "properties": {
            "nrn": {"type": "string"},
            "category": {"type": ["string", "null"]},
        }, "required": ["nrn"]},
        handler=_registry_lookup,
    ),
    Tool(
        name="alert_search",
        description="Search the NAFDAC public-alert registry for a match on NRN and batch.",
        parameters={"type": "object", "properties": {
            "nrn": {"type": ["string", "null"]},
            "batch": {"type": ["string", "null"]},
            "product": {"type": ["string", "null"]},
        }},
        handler=_alert_search,
    ),
    Tool(
        name="compare_to_alert",
        description="Return the known visual differences documented for a specific NAFDAC alert.",
        parameters={"type": "object", "properties": {
            "alert_id": {"type": "string"},
        }, "required": ["alert_id"]},
        handler=_compare_to_alert,
    ),
    Tool(
        name="sanity_checks",
        description="Return the deterministic label sanity flags already computed by code.",
        parameters={"type": "object", "properties": {}},
        handler=_sanity_checks,
    ),
    Tool(
        name="mas_guide",
        description="Return the SMS short code for a Mobile Authentication Service provider.",
        parameters={"type": "object", "properties": {
            "provider": {"type": "string"},
        }, "required": ["provider"]},
        handler=_mas_guide,
    ),
    Tool(
        name="ask_user",
        description="Ask the user a question mid-run (for example, to photograph another panel).",
        parameters={"type": "object", "properties": {
            "question": {"type": "string"},
            "kind": {"type": "string", "enum": ["photo", "confirm", "choice"]},
        }, "required": ["question", "kind"]},
        handler=_ask_user,
    ),
    Tool(
        name="finish",
        description="Finish the investigation and return the final report. Call this once when done.",
        parameters={"type": "object", "properties": {
            "report": {"type": "object"},
        }, "required": ["report"]},
        handler=_finish,
    ),
]

TOOL_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}


def tool_schemas() -> list[dict]:
    """Return the OpenAI-compatible function-calling schemas for all tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS
    ]
