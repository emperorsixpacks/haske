"""Mock extractor: reads canned extraction results from fixtures keyed by filename."""

from __future__ import annotations

import json
from pathlib import Path

from ..app.config import Settings
from .schemas import ExtractionResult
from .vision import Extractor

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class MockExtractor(Extractor):
    def __init__(self, settings: Settings, fixtures_dir: Path | None = None):
        self.settings = settings
        self.fixtures_dir = fixtures_dir or _FIXTURES_DIR

    def extract(self, image_bytes: bytes, filename: str | None = None) -> ExtractionResult:
        key = filename or "default"
        fixture = self.fixtures_dir / f"{key}.json"
        if not fixture.exists():
            fixture = self.fixtures_dir / "default.json"
        if not fixture.exists():
            return ExtractionResult(legibility_notes=["unreadable: no fixture"])
        data = json.loads(fixture.read_text())
        return ExtractionResult.model_validate(data)


def get_extractor(settings: Settings) -> Extractor:
    if settings.mock_mode:
        return MockExtractor(settings)
    return VisionExtractor(settings)
