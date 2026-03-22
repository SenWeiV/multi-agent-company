from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.company.models import WorkTicket
from app.core.config import get_settings
from app.store import build_model_store

client = TestClient(app)


def test_root_endpoint_returns_bootstrap_status() -> None:
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "bootstrap_ready"
    assert payload["api_prefix"] == "/api/v1"


def test_health_endpoints_return_ok() -> None:
    root_response = client.get("/healthz")
    api_response = client.get("/api/v1/health")
    compat_response = client.get("/api/v1/system/health")

    assert root_response.status_code == 200
    assert api_response.status_code == 200
    assert compat_response.status_code == 200
    assert root_response.json()["status"] == "ok"
    assert api_response.json()["status"] == "ok"
    assert compat_response.json()["status"] == "ok"
    assert "state_store_backend" in api_response.json()


def test_postgres_backend_persists_work_ticket_beyond_single_service_instance() -> None:
    if get_settings().state_store_backend != "postgres":
        pytest.skip("requires postgres state store backend")

    response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "让工程帮我做这个小任务，先出一个技术方案"},
    )
    assert response.status_code == 200
    ticket_id = response.json()["work_ticket"]["ticket_id"]

    independent_store = build_model_store(WorkTicket, "ticket_id", "work_tickets")
    persisted_ticket = independent_store.get(ticket_id)

    assert persisted_ticket is not None
    assert persisted_ticket.ticket_id == ticket_id
