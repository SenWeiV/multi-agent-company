from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_persona_packs_endpoint_exposes_agency_agents_registry() -> None:
    response = client.get("/api/v1/persona/persona-packs")

    assert response.status_code == 200
    payload = response.json()
    role_names = {item["role_name"] for item in payload}

    assert "Backend Architect" in role_names
    assert "Agents Orchestrator" in role_names
    assert len(payload) >= 20
    backend_architect = next(item for item in payload if item["role_name"] == "Backend Architect")
    assert backend_architect["source_url"].endswith("/engineering/engineering-backend-architect.md")


def test_employee_pack_compiler_returns_composite_engineering_pack() -> None:
    response = client.get("/api/v1/persona/employee-packs/engineering-lead")

    assert response.status_code == 200
    payload = response.json()

    assert payload["employee_id"] == "engineering-lead"
    assert payload["department"] == "Engineering"
    assert len(payload["source_persona_packs"]) == 3
    assert payload["memory_profile"]["private_namespace"] == "employee:engineering-lead"
    assert payload["memory_profile"]["department_namespace"] == "department:engineering"
    assert "build" in payload["agent_profile"]["capabilities"]
    assert "code" in payload["agent_profile"]["allowed_tool_classes"]
    assert len(payload["professional_skills"]) >= 30
    assert len(payload["general_skills"]) >= 10
    assert payload["professional_skills"][0]["source_ref"]["repo_name"]


def test_employee_skill_pack_endpoint_exposes_real_github_backed_skill_catalog() -> None:
    response = client.get("/api/v1/persona/employee-packs/product-lead/skills")

    assert response.status_code == 200
    payload = response.json()

    assert payload["employee_id"] == "product-lead"
    assert len(payload["professional_skills"]) >= 30
    assert len(payload["general_skills"]) >= 10
    first_skill = payload["professional_skills"][0]
    assert first_skill["skill_id"]
    assert first_skill["source_ref"]["repo_url"].startswith("https://github.com/")
    assert first_skill["source_ref"]["commit_sha"]
    assert first_skill["source_ref"]["path"]
    assert first_skill["source_ref"]["license"]


def test_skill_catalog_validation_endpoint_returns_ok() -> None:
    response = client.get("/api/v1/persona/skill-catalog/validate")

    assert response.status_code == 200
    payload = response.json()

    assert payload["ok"] is True
    assert payload["professional_skill_count_by_employee"]["chief-of-staff"] >= 30
    assert payload["general_skill_count_by_employee"]["engineering-lead"] >= 10
    assert payload["issues"] == []


def test_core_only_employee_packs_match_v1_core_departments() -> None:
    response = client.get("/api/v1/persona/employee-packs", params={"core_only": "true"})

    assert response.status_code == 200
    payload = response.json()

    employee_ids = {item["employee_id"] for item in payload}
    assert employee_ids == {
        "chief-of-staff",
        "product-lead",
        "research-lead",
        "delivery-lead",
        "design-lead",
        "engineering-lead",
        "quality-lead",
    }
