"""Orchestration: extraction -> NRN -> lookup -> match -> consistency -> verdict -> explanation."""

from __future__ import annotations

import base64
import datetime as dt

from ..extraction.consistency import check_consistency
from ..extraction.explain import Explainer, get_explainer
from ..extraction.schemas import ExtractionResult
from ..extraction.vision import Extractor
from ..observations.store import ObservationStore
from ..registries.alerts import get_alert_registry
from ..registries.matcher import match
from ..registries.models import LookupResult, RegistryCategory
from ..registries.nrn import normalise_nrn
from ..registries.router import RegistryRouter
from ..registries.store import Store
from ..verdict.engine import decide
from .config import Settings
from .schemas import AlertReference, CheckResponse, NrnInfo, TraceEventModel

_GUESS_TO_CATEGORY = {
    "drug": RegistryCategory.DRUG,
    "medicine": RegistryCategory.DRUG,
    "pharmaceutical": RegistryCategory.DRUG,
    "vaccine": RegistryCategory.VACCINE,
    "device": RegistryCategory.DEVICE,
    "veterinary": RegistryCategory.VETERINARY,
    "vet": RegistryCategory.VETERINARY,
    "herbal": RegistryCategory.HERBAL,
    "food": RegistryCategory.FOOD,
    "water": RegistryCategory.WATER,
    "general": RegistryCategory.GENERAL,
    "cosmetic": RegistryCategory.COSMETIC,
    "soap": RegistryCategory.SOAP,
}


def category_from_guess(guess: str | None) -> RegistryCategory:
    return _GUESS_TO_CATEGORY.get((guess or "").strip().lower(), RegistryCategory.UNKNOWN)


def _build_alert_reference(alert_finding) -> AlertReference | None:
    """Convert an AlertFinding into the API-facing AlertReference."""
    if alert_finding is None:
        return None
    alert = alert_finding.alert
    return AlertReference(
        kind=alert_finding.kind,
        alert_no=alert.alert_no,
        date=alert.date,
        product=alert.product,
        nrn=alert.nrn,
        source_url=alert.source_url,
        known_differences=list(alert.known_differences),
        quoted_text=alert.quoted_text,
        matched_batch=alert_finding.matched.batch if alert_finding.matched else None,
        fuzzy=alert_finding.fuzzy,
    )


class CheckService:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        extractor: Extractor,
        router: RegistryRouter,
        explainer: Explainer | None = None,
        obs_store: ObservationStore | None = None,
    ):
        self.settings = settings
        self.store = store
        self.extractor = extractor
        self.router = router
        self.explainer = explainer or get_explainer(settings)
        self.obs_store = obs_store

    def check_image(self, image_bytes: bytes, filename: str | None = None) -> CheckResponse:
        extraction = self.extractor.extract(image_bytes, filename)
        response = self._evaluate(extraction)
        # Escalation ladder: only run the investigator agent on a trigger, and only when
        # enabled. The deterministic response is always the fallback.
        if self.settings.investigator_enabled and self._should_escalate(response, extraction):
            outcome = self._run_agent(extraction, image_bytes, response)
            response.agent_trace = [TraceEventModel(**e) for e in outcome.trace.to_list()]
            response.trace_summary = outcome.trace.summary_line()
            response.agent_report = outcome.report
        return response

    def check_fields(self, fields: dict) -> CheckResponse:
        extraction = ExtractionResult(
            product_name=fields.get("product_name"),
            nrn=fields.get("nrn"),
            batch=fields.get("batch"),
            manufacture_date=fields.get("manufacture_date"),
            expiry_date=fields.get("expiry_date"),
            manufacturer=fields.get("manufacturer"),
            strength=fields.get("strength"),
            category_guess=fields.get("category_guess"),
        )
        return self._evaluate(extraction)

    def _evaluate(self, extraction: ExtractionResult) -> CheckResponse:
        category = category_from_guess(extraction.category_guess)
        nrn = normalise_nrn(extraction.nrn)
        retrieved_at = self._snapshot_time()

        if not nrn.valid:
            lookup = LookupResult.incomplete(
                nrn.error or "invalid_nrn",
                nrn=nrn.canonical,
                source=self.router.client_for(category).name,
            )
        else:
            lookup = self.router.lookup(nrn.canonical, category)

        match_result = match(extraction.as_label_dict(), lookup.records)

        # Evidence-First: match against the NAFDAC public-alert registry (deterministic).
        alert_finding = get_alert_registry().lookup(nrn.canonical, extraction.batch)

        # Tier 2: deterministic label consistency checks.
        consistency = check_consistency(extraction)

        # Tier 3: batch conflict check against the observation ledger.
        batch_conflict_note: str | None = None
        if (
            self.obs_store is not None
            and nrn.canonical
            and extraction.batch
        ):
            conflict = self.obs_store.conflict_check(
                nrn.canonical,
                extraction.batch,
                extraction.expiry_date,
            )
            batch_conflict_note = conflict.to_note()
            # Record this observation for future conflict detection.
            # Ignore rate-limit errors silently; they should not affect the verdict.
            try:
                self.obs_store.record(
                    nrn=nrn.canonical,
                    batch=extraction.batch,
                    mfg_date=extraction.manufacture_date,
                    expiry_date=extraction.expiry_date,
                    manufacturer=extraction.manufacturer,
                )
            except Exception:  # noqa: BLE001
                pass

        verdict = decide(
            lookup,
            match_result,
            category,
            retrieved_at,
            consistency_flags=consistency.flags,
            batch_conflict_note=batch_conflict_note,
            alert_finding=alert_finding,
        )

        alert_ref = _build_alert_reference(alert_finding)

        # Ask the LLM to write a plain-language explanation of the already-decided verdict.
        evidence_note = verdict.evidence[0].note if verdict.evidence else None
        explanation = self.explainer.explain(
            verdict_code=verdict.code.value,
            product_name=extraction.product_name,
            nrn=nrn.canonical,
            category=category.value,
            evidence_note=evidence_note,
            consistency_flags=consistency.flags,
            batch_conflict_note=batch_conflict_note,
        )
        if explanation:
            verdict.explanation = explanation

        return CheckResponse(
            extraction=extraction,
            nrn=NrnInfo(
                raw=nrn.raw,
                canonical=nrn.canonical,
                is_barcode=nrn.is_barcode,
                ambiguous_o_zero=nrn.ambiguous_o_zero,
                error=nrn.error,
                valid=nrn.valid,
            ),
            match_outcome=match_result.outcome.value,
            verdict=verdict,
            alert=alert_ref,
        )

    def investigate(self, image_bytes: bytes, filename: str | None = None) -> dict:
        """Run the investigator agent as an escalation layer over the deterministic check."""
        extraction = self.extractor.extract(image_bytes, filename)
        baseline = self._evaluate(extraction)
        outcome = self._run_agent(extraction, image_bytes, baseline)
        return {
            "outcome": outcome.outcome,
            "report": outcome.report,
            "question": outcome.question,
            "trace": outcome.trace.to_list(),
            "trace_summary": outcome.trace.summary_line(),
            "rounds": outcome.rounds,
            "fallback_verdict": baseline.verdict.code.value,
            "fallback_alert": baseline.alert.model_dump() if baseline.alert else None,
        }

    def _run_agent(self, extraction: ExtractionResult, image_bytes: bytes, baseline: CheckResponse):
        from ..agent.loop import AgentOutcome, run_agent
        from ..agent.tools import AgentContext

        category = category_from_guess(extraction.category_guess)
        consistency = check_consistency(extraction)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        ctx = AgentContext(
            settings=self.settings,
            extractor=self.extractor,
            router=self.router,
            alert_registry=get_alert_registry(),
            images=[{"id": "main", "data_url": f"data:image/jpeg;base64,{b64}"}],
            extraction=extraction,
            nrn=baseline.nrn,
            category=category,
            consistency_flags=consistency.flags,
        )
        return run_agent(settings=self.settings, ctx=ctx)

    def _should_escalate(self, response: CheckResponse, extraction: ExtractionResult) -> bool:
        """Escalate to the agent only when there is a real signal to investigate."""
        if response.alert is not None:
            return True
        return bool(check_consistency(extraction).flags)

    def _snapshot_time(self) -> dt.datetime | None:
        snap = self.store.latest_snapshot()
        if snap:
            return dt.datetime.fromisoformat(snap["fetched_at"])
        return None
