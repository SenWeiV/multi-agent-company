from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_idea_capture_writes_company_shared_ceo_intent_memory() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "我有个想法，先记一下以后再说"},
    )

    assert intake_response.status_code == 200
    ticket_id = intake_response.json()["work_ticket"]["ticket_id"]

    memory_response = client.get(f"/api/v1/memory/work-tickets/{ticket_id}")
    assert memory_response.status_code == 200
    payload = memory_response.json()

    assert any(record["scope"] == "company_shared" for record in payload)
    assert any("ceo_intent" in record["tags"] for record in payload)


def test_department_task_writes_department_shared_memory_and_recall_is_department_scoped() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "让工程帮我做这个小任务，先出一个技术方案"},
    )
    assert intake_response.status_code == 200
    ticket_id = intake_response.json()["work_ticket"]["ticket_id"]

    memory_response = client.get(f"/api/v1/memory/work-tickets/{ticket_id}")
    payload = memory_response.json()
    assert any(record["scope"] == "department_shared" and record["scope_id"] == "Engineering" for record in payload)

    engineering_recall = client.post(
        "/api/v1/memory/recall",
        json={
            "scope_filter": ["department_shared"],
            "tags": ["department_task", "Engineering"],
            "requester_id": "engineering-lead",
            "requester_department": "Engineering",
        },
    )
    design_recall = client.post(
        "/api/v1/memory/recall",
        json={
            "scope_filter": ["department_shared"],
            "tags": ["department_task", "Engineering"],
            "requester_id": "design-lead",
            "requester_department": "Design & UX",
        },
    )

    assert engineering_recall.status_code == 200
    assert design_recall.status_code == 200
    assert len(engineering_recall.json()) >= 1
    assert design_recall.json() == []


def test_memory_recall_enforces_agent_private_visibility() -> None:
    write_response = client.post(
        "/api/v1/memory/write",
        json={
            "namespace_id": "employee:engineering-lead",
            "owner_id": "engineering-lead",
            "kind": "episodic",
            "content": "个人调试经验：先检查 release checklist。",
            "tags": ["personal", "engineering"],
        },
    )
    assert write_response.status_code == 200

    allowed_recall = client.post(
        "/api/v1/memory/recall",
        json={
            "scope_filter": ["agent_private"],
            "tags": ["personal", "engineering"],
            "requester_id": "engineering-lead",
            "requester_department": "Engineering",
        },
    )
    denied_recall = client.post(
        "/api/v1/memory/recall",
        json={
            "scope_filter": ["agent_private"],
            "tags": ["personal", "engineering"],
            "requester_id": "design-lead",
            "requester_department": "Design & UX",
        },
    )

    assert allowed_recall.status_code == 200
    assert denied_recall.status_code == 200
    assert len(allowed_recall.json()) >= 1
    assert denied_recall.json() == []


def test_formal_project_checkpoint_contains_memory_refs_and_override_supersedes_initial_memory() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    assert len(intake_payload["checkpoint"]["memory_refs"]) >= 3

    quality_response = client.post(
        "/api/v1/quality/evaluate",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "verdict": "no_go",
            "summary": "当前路径证据不足，需要回退后重做。",
            "evidence_points": ["missing release checklist"],
        },
    )
    assert quality_response.status_code == 200

    override_response = client.post(
        "/api/v1/governance/override-recovery",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "new_direction": "回到上一个 checkpoint，补齐 release checklist 后再推进",
            "summary": "CEO 决定回退并改向。",
        },
    )
    assert override_response.status_code == 200
    override_payload = override_response.json()

    memory_response = client.get(f"/api/v1/memory/work-tickets/{intake_payload['work_ticket']['ticket_id']}")
    assert memory_response.status_code == 200
    memory_payload = memory_response.json()

    assert any(
        record["superseded_by"] == override_payload["override_decision"]["decision_id"] for record in memory_payload
    )
    assert any(
        "override_recovery" in record["tags"] and record["superseded_by"] is None for record in memory_payload
    )
