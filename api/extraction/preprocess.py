"""Image preprocessing hook.

Milestone 1: pass-through. Milestone 2 will crop label regions with SAM 3.1 before the
vision model reads them, improving NRN extraction accuracy on cluttered backgrounds.

Milestone 2 tasks:
- Integrate segment-anything-model (SAM 3.1) to detect and crop the product label region.
- The crop_to_label() function below is the insertion point; replace the pass-through body.
- Keep the preprocess() signature stable; call sites in vision.py never change.
"""

from __future__ import annotations


def crop_to_label(image_bytes: bytes) -> bytes:
    """Crop image bytes to the product label region using SAM 3.1.

    Milestone 2 stub: returns the original bytes unchanged.
    Replace this body with SAM inference when the model is available.
    """
    # TODO(milestone-2): run SAM 3.1 segmentation, select label mask, crop and return.
    return image_bytes


def preprocess(image_bytes: bytes, filename: str | None = None) -> bytes:
    """Return image bytes ready for the vision model.

    Currently calls crop_to_label() which is a pass-through in milestone 1.
    """
    return crop_to_label(image_bytes)
