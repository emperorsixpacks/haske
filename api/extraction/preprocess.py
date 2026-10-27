"""Image preprocessing hook.

Milestone 1 is a no-op. Milestone 2 will crop label regions here with SAM 3.1 before the
vision model reads them. The interface is stable now so the call sites never change.
"""

from __future__ import annotations


def preprocess(image_bytes: bytes, filename: str | None = None) -> bytes:
    """Return image bytes ready for the vision model. Currently a pass-through."""
    # TODO(milestone-2): run SAM 3.1 to crop label regions before OCR extraction.
    return image_bytes
