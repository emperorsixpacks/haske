import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HASKE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("META_API_KEY", raising=False)
    from api.app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_registry_status_after_demo_seed(client):
    r = client.get("/v1/registry/status")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "greenbook"
    assert body["record_count"] >= 3
    assert body["snapshot_date"] is not None


def test_check_fields_endpoint(client):
    r = client.post(
        "/v1/check/fields",
        json={
            "product_name": "Paracetamol Tablets 500mg",
            "manufacturer": "Acme Pharma Ltd",
            "strength": "500mg",
            "nrn": "A4-0123",
            "category_guess": "drug",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"]["code"] == "CONSISTENT_WITH_REGISTRY"
    assert body["nrn"]["canonical"] == "A4-0123"
    assert body["verdict"]["footer"] is not None


def test_check_image_endpoint(client):
    r = client.post("/v1/check", files={"image": ("photo.jpg", b"\xff\xd8fake", "image/jpeg")})
    assert r.status_code == 200
    body = r.json()
    assert body["extraction"]["nrn"] == "A4-0123"
    assert body["verdict"]["code"] in {"CONSISTENT_WITH_REGISTRY", "NOT_FOUND_IN_REGISTRY"}
