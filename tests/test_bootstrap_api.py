from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_company_bootstrap_returns_default_profile() -> None:
    response = client.get("/api/v1/bootstrap/company")

    assert response.status_code == 200
    payload = response.json()
    assert payload["company_id"] == "default"
    assert "Executive Office" in payload["default_departments"]
    assert len(payload["budget_policy"]) == 4


def test_department_bootstrap_returns_full_org_chart() -> None:
    response = client.get("/api/v1/bootstrap/departments")

    assert response.status_code == 200
    payload = response.json()
    department_names = [item["department_name"] for item in payload]

    assert len(payload) == 12
    assert "Engineering" in department_names
    assert "Trust / Security / Legal" in department_names

