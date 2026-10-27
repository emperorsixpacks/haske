"""Fixed message templates for verdicts.

Language rules enforced here:
- Say "indicators found" and "the register shows"; never overstate.
- Never write "fake" or "counterfeit" unless a cited official alert matches product AND
  batch (milestone 2). ALERT_MATCH is reserved and does not carry those words yet.
- Never certify a product as genuine; the best positive result is "consistent with the
  registry, which does not prove authenticity".
"""

from __future__ import annotations

from .engine import VerdictCode

TITLES: dict[VerdictCode, str] = {
    VerdictCode.CONSISTENT_WITH_REGISTRY: "Consistent with the registry",
    VerdictCode.REGISTRY_MISMATCH: "Registry mismatch",
    VerdictCode.NOT_FOUND_IN_REGISTRY: "Not found in the registry",
    VerdictCode.EXPIRED_OR_INACTIVE: "Registration expired or inactive",
    VerdictCode.ALERT_MATCH: "Matches an official alert",
    VerdictCode.CANNOT_CONFIRM: "Cannot confirm",
}

MESSAGES: dict[VerdictCode, str] = {
    VerdictCode.CONSISTENT_WITH_REGISTRY: (
        "The details on the label are consistent with the registry, which does not prove "
        "authenticity. Indicators found: the registration number exists and the product "
        "name and manufacturer agree with the register."
    ),
    VerdictCode.REGISTRY_MISMATCH: (
        "Indicators found: the registration number exists, but the register shows it "
        "belongs to a different product. This is a sign the product may be mislabelled."
    ),
    VerdictCode.NOT_FOUND_IN_REGISTRY: (
        "The registration number was not found in the registry. This can mean the number "
        "is invalid, or the product is not listed in the sources we can check."
    ),
    VerdictCode.EXPIRED_OR_INACTIVE: (
        "The register shows this registration is expired or inactive. The number exists "
        "and the product details agree, but the registration is not current."
    ),
    VerdictCode.ALERT_MATCH: (
        "This product matches a cited official alert. See the evidence for the source."
    ),
    VerdictCode.CANNOT_CONFIRM: (
        "There is not enough evidence to confirm whether this product matches the "
        "registry. The register may be unavailable, the number may be shared, or the "
        "label could not be read reliably."
    ),
}

# Footer appended to every medicines (drug/vaccine/herbal/device/vet) verdict. It must give
# no dosing or take/stop advice.
MEDICINES_FOOTER = (
    "If you have any concern about this medicine, ask a pharmacist or another qualified "
    "health worker, and report your suspicions to NAFDAC. This tool does not give advice "
    "on whether to take, change, or stop a medicine."
)

# Message returned when a user asks for medical advice (dosing, taking, stopping).
PHARMACIST_REDIRECT = (
    "This tool does not give advice on whether to take, change, or stop a medicine. Ask a "
    "pharmacist or another qualified health worker."
)
