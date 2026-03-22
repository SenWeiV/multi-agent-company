from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_classify_idea_capture_command() -> None:
    response = client.post(
        "/api/v1/commands/classify",
        json={"intent": "我有个想法，先记一下以后再说"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interaction_mode"] == "idea_capture"
    assert payload["participation_scope"] == "executive_only"
    assert payload["work_ticket"]["ticket_type"] == "idea_capture"


def test_classify_department_task_command() -> None:
    response = client.post(
        "/api/v1/commands/classify",
        json={"intent": "让工程帮我做这个小任务，先出一个技术方案"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interaction_mode"] == "department_task"
    assert "Engineering" in payload["recommended_departments"]
    assert payload["goal_request"]["goal_lineage_ref"].startswith("gl-")


def test_classify_formal_project_command() -> None:
    response = client.post(
        "/api/v1/commands/classify",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["interaction_mode"] == "formal_project"
    assert payload["participation_scope"] == "full_project_chain"
    assert payload["goal_request"]["deliverables"] == [
        "Deliverable",
        "EvidenceArtifact",
        "Checkpoint",
    ]
