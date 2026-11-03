"""Deterministic image cropping for two-pass reading.

Boxes are normalized (0..1). crop_to_box clamps to the image bounds, enforces a minimum
size, and re-encodes as JPEG. No model calls here.
"""

from __future__ import annotations

import io

from PIL import Image

_MIN_SIDE = 48


def clamp_box(box: list[float], width: int, height: int) -> tuple[float, float, float, float]:
    """Clamp a normalized box to the image bounds, preserving a minimum footprint."""
    x0, y0, x1, y1 = (float(v) for v in box)
    x0 = max(0.0, min(x0, 1.0))
    y0 = max(0.0, min(y0, 1.0))
    x1 = max(0.0, min(x1, 1.0))
    y1 = max(0.0, min(y1, 1.0))
    if x1 <= x0:
        x1 = min(1.0, x0 + 0.02)
    if y1 <= y0:
        y1 = min(1.0, y0 + 0.02)
    return x0, y0, x1, y1


def crop_to_box(image_bytes: bytes, box: list[float], min_side: int = _MIN_SIDE) -> bytes:
    """Crop image_bytes to a normalized box and return JPEG bytes."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = img.size
    x0, y0, x1, y1 = clamp_box(box, width, height)

    left = int(x0 * width)
    top = int(y0 * height)
    right = int(x1 * width)
    bottom = int(y1 * height)

    left = max(0, left)
    top = max(0, top)
    right = min(width, right)
    bottom = min(height, bottom)

    # Enforce a minimum crop size so OCR has enough pixels.
    if right - left < min_side:
        right = min(width, left + min_side)
    if bottom - top < min_side:
        bottom = min(height, top + min_side)
    if right - left < 1 or bottom - top < 1:
        return image_bytes

    cropped = img.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=95)
    return buf.getvalue()
