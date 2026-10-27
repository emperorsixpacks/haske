"""FastAPI application: /v1/check, /v1/check/fields, /v1/health, /v1/registry/status."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from ..extraction.mock import get_extractor
from ..registries.demo import seed_demo
from ..registries.fake import FakeNapamsClient
from ..registries.greenbook import GreenbookClient
from ..registries.napams import NapamsClient
from ..registries.router import RegistryRouter
from ..registries.store import Store
from .config import get_settings
from .schemas import CheckFieldsRequest, CheckResponse, RegistryStatus
from .service import CheckService

logger = logging.getLogger("haske")

# Non-identifying metrics only: counts and latency, never photos or labels.
_metrics = {"checks": 0, "field_checks": 0}


def _build_service():
    settings = get_settings()
    store = Store(settings.db_path)
    if settings.mock_mode:
        seed_demo(store)
        napams = FakeNapamsClient({})
    else:
        napams = NapamsClient(settings)
    router = RegistryRouter(greenbook=GreenbookClient(store), napams=napams)
    extractor = get_extractor(settings)
    return settings, store, CheckService(settings, store, extractor, router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings, store, service = _build_service()
    app.state.settings = settings
    app.state.store = store
    app.state.service = service
    logger.info("haske started (mock_mode=%s)", settings.mock_mode)
    yield
    store.close()


app = FastAPI(title="Haske", version="0.1.0", lifespan=lifespan)


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/registry/status", response_model=RegistryStatus)
def registry_status() -> RegistryStatus:
    store: Store = app.state.store
    snap = store.latest_snapshot()
    return RegistryStatus(
        source="greenbook",
        snapshot_date=snap["fetched_at"] if snap else None,
        record_count=store.record_count(),
    )


@app.post("/v1/check", response_model=CheckResponse)
async def check_image(image: UploadFile = File(...)) -> CheckResponse:
    _metrics["checks"] += 1
    service: CheckService = app.state.service
    data = await image.read()
    return service.check_image(data, filename=image.filename)


@app.post("/v1/check/fields", response_model=CheckResponse)
async def check_fields(fields: CheckFieldsRequest) -> CheckResponse:
    _metrics["field_checks"] += 1
    service: CheckService = app.state.service
    return service.check_fields(fields.model_dump())
