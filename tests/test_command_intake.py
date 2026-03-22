from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_intake_creates_work_ticket_run_trace_and_formal_project_task_graph() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["work_ticket"]["status"] == "active"
    assert payload["run_trace"]["status"] == "routed"
    assert payload["task_graph"]["interaction_mode"] == "formal_project"
    assert payload["task_graph"]["work_ticket_ref"] == payload["work_ticket"]["ticket_id"]
    assert payload["run_trace"]["work_ticket_ref"] == payload["work_ticket"]["ticket_id"]
    assert payload["work_ticket"]["runtrace_ref"] == payload["run_trace"]["runtrace_id"]
    assert any(check["status"] == "warning" for check in payload["budget_checks"])
    assert payload["trigger_context"]["status"] == "accepted"
    assert payload["checkpoint"]["kind"] == "formal"
    assert payload["checkpoint"]["taskgraph_ref"] == payload["task_graph"]["taskgraph_id"]
    assert len(payload["task_graph"]["nodes"]) == 6
    assert payload["task_graph"]["nodes"][0]["owner_department"] == "Executive Office"
    assert payload["task_graph"]["nodes"][-1]["owner_department"] == "Quality"


def test_intake_skips_task_graph_for_idea_capture() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "我有个想法，先记一下以后再说"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_graph"] is None
    assert payload["work_ticket"]["status"] == "captured"
    event_types = [event["event_type"] for event in payload["run_trace"]["events"]]
    assert "task_graph_skipped" in event_types


def test_quick_consult_defaults_to_non_executable_without_discovery_recipe() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "你怎么看这个想法，给我一点建议"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["classification"]["interaction_mode"] == "quick_consult"
    assert payload["classification"]["workflow_recipe"] == "default"
    assert payload["task_graph"] is None
    assert payload["work_ticket"]["status"] == "consulting"


def test_discovery_consult_creates_discovery_synthesis_task_graph() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "研究一下本周 AI 产品趋势，并综合成产品与设计建议"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["classification"]["interaction_mode"] == "quick_consult"
    assert payload["classification"]["workflow_recipe"] == "discovery_synthesis"
    assert payload["classification"]["participation_scope"] == "multi_department"
    assert payload["task_graph"]["workflow_recipe"] == "discovery_synthesis"
    assert payload["run_trace"]["workflow_recipe"] == "discovery_synthesis"
    assert payload["work_ticket"]["status"] == "consulting"
    assert len(payload["task_graph"]["nodes"]) == 5
    assert payload["task_graph"]["nodes"][0]["owner_department"] == "Executive Office"
    assert {node["owner_department"] for node in payload["task_graph"]["nodes"][1:4]} == {
        "Research & Intelligence",
        "Product",
        "Design & UX",
    }
    assert payload["task_graph"]["nodes"][-1]["owner_department"] == "Executive Office"
    assert payload["task_graph"]["nodes"][-1]["output_kind"] == "CrossAgentSynthesis"


def test_launch_growth_consult_creates_launch_growth_task_graph() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "产品里程碑准备上线，给我一套增长、支持和用户反馈闭环方案"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["classification"]["interaction_mode"] == "quick_consult"
    assert payload["classification"]["workflow_recipe"] == "launch_growth"
    assert payload["classification"]["participation_scope"] == "multi_department"
    assert payload["task_graph"]["workflow_recipe"] == "launch_growth"
    assert payload["run_trace"]["workflow_recipe"] == "launch_growth"
    assert payload["work_ticket"]["status"] == "consulting"
    assert len(payload["task_graph"]["nodes"]) == 4
    assert payload["task_graph"]["nodes"][0]["owner_department"] == "Executive Office"
    assert {node["owner_department"] for node in payload["task_graph"]["nodes"][1:3]} == {
        "Growth & Marketing",
        "Customer Success & Support",
    }
    assert payload["task_graph"]["nodes"][-1]["owner_department"] == "Executive Office"
    assert payload["task_graph"]["nodes"][-1]["output_kind"] == "LaunchDecisionBrief"


def test_intake_blocks_when_budget_estimate_exceeds_hard_limit_without_override() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "让工程帮我做这个小任务，先出一个技术方案",
            "budget_estimate": 150,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_graph"] is None
    assert payload["work_ticket"]["status"] == "budget_blocked"
    assert payload["run_trace"]["status"] == "blocked"
    assert any(check["scope"] == "task" and check["status"] == "blocked" for check in payload["budget_checks"])


def test_scheduled_heartbeat_is_allowed_only_for_predefined_recurring_work() -> None:
    accepted = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "研究一下本周 AI 产品趋势",
            "trigger_type": "scheduled_heartbeat",
        },
    )
    rejected = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "让工程修一个线上问题",
            "trigger_type": "scheduled_heartbeat",
        },
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 200
    assert accepted.json()["trigger_context"]["status"] == "accepted"
    assert accepted.json()["run_trace"]["status"] == "routed"
    assert accepted.json()["classification"]["workflow_recipe"] == "discovery_synthesis"
    assert accepted.json()["task_graph"]["workflow_recipe"] == "discovery_synthesis"
    assert rejected.json()["trigger_context"]["status"] == "rejected"
    assert rejected.json()["work_ticket"]["status"] == "trigger_rejected"
    assert rejected.json()["run_trace"]["status"] == "blocked"


def test_post_launch_heartbeat_can_route_into_launch_growth_loop() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "整理本周用户反馈、留存风险和增长建议，形成上线后支持摘要",
            "trigger_type": "scheduled_heartbeat",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trigger_context"]["status"] == "accepted"
    assert payload["classification"]["workflow_recipe"] == "launch_growth"
    assert payload["task_graph"]["workflow_recipe"] == "launch_growth"
    assert {node["owner_department"] for node in payload["task_graph"]["nodes"][1:3]} == {
        "Growth & Marketing",
        "Customer Success & Support",
    }


def test_control_plane_retrieval_endpoints_return_created_objects() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "让工程帮我做这个小任务，先出一个技术方案",
            "checkpoint_requested": True,
        },
    )
    payload = intake_response.json()

    ticket_id = payload["work_ticket"]["ticket_id"]
    runtrace_id = payload["run_trace"]["runtrace_id"]
    taskgraph_id = payload["task_graph"]["taskgraph_id"]
    checkpoint_id = payload["checkpoint"]["checkpoint_id"]

    ticket_response = client.get(f"/api/v1/control-plane/work-tickets/{ticket_id}")
    runtrace_response = client.get(f"/api/v1/control-plane/run-traces/{runtrace_id}")
    taskgraph_response = client.get(f"/api/v1/control-plane/task-graphs/{taskgraph_id}")
    checkpoint_response = client.get(f"/api/v1/control-plane/checkpoints/{checkpoint_id}")
    ticket_checkpoints_response = client.get(f"/api/v1/control-plane/work-tickets/{ticket_id}/checkpoints")

    assert ticket_response.status_code == 200
    assert runtrace_response.status_code == 200
    assert taskgraph_response.status_code == 200
    assert checkpoint_response.status_code == 200
    assert ticket_checkpoints_response.status_code == 200
    assert ticket_response.json()["runtrace_ref"] == runtrace_id
    assert runtrace_response.json()["taskgraph_ref"] == taskgraph_id
    assert taskgraph_response.json()["nodes"][0]["owner_department"] == "Engineering"
    assert checkpoint_response.json()["taskgraph_ref"] == taskgraph_id
    assert len(ticket_checkpoints_response.json()) == 1


def test_department_task_can_create_lightweight_checkpoint_on_request() -> None:
    response = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "让工程帮我做这个小任务，先出一个技术方案",
            "checkpoint_requested": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["checkpoint"]["kind"] == "lightweight"
    assert payload["checkpoint"]["stage"] == "department_task_lightweight"
    assert payload["checkpoint"]["taskgraph_ref"] == payload["task_graph"]["taskgraph_id"]


def test_checkpoint_restore_marks_ticket_and_trace() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    checkpoint_id = intake_response.json()["checkpoint"]["checkpoint_id"]

    restore_response = client.post(f"/api/v1/control-plane/checkpoints/{checkpoint_id}/restore")

    assert restore_response.status_code == 200
    payload = restore_response.json()
    assert payload["work_ticket"]["status"] == "restored"
    assert payload["run_trace"]["status"] == "routed"
    assert payload["task_graph"]["status"] == "ready"
    assert payload["task_graph"]["nodes"][0]["status"] == "ready"
    event_types = [event["event_type"] for event in payload["run_trace"]["events"]]
    assert "checkpoint_restored" in event_types


def test_quality_no_go_creates_evidence_and_escalates_ticket() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    response = client.post(
        "/api/v1/quality/evaluate",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "verdict": "no_go",
            "summary": "缺少关键交付证据，暂不放行。",
            "evidence_points": ["no demo link", "missing acceptance notes"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_artifact"]["artifact_type"] == "quality_evidence"
    assert payload["decision_record"]["verdict"] == "no_go"
    assert payload["checkpoint"]["verdict_state"] == "no_go"
    assert payload["work_ticket"]["status"] == "quality_no_go"
    assert payload["run_trace"]["status"] == "escalated"
    assert payload["task_graph"]["status"] == "escalated"


def test_review_decision_approval_uses_existing_evidence_and_updates_state() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    quality_response = client.post(
        "/api/v1/quality/evaluate",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "verdict": "go",
            "summary": "证据齐全，可以进入 CEO review。",
            "evidence_points": ["checkpoint exists", "quality evidence attached"],
        },
    )
    quality_payload = quality_response.json()

    review_response = client.post(
        "/api/v1/approvals/review-decision",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "decision": "approved",
            "summary": "CEO 批准继续推进。",
        },
    )

    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["approval_gate"]["status"] == "approved"
    assert payload["decision_record"]["verdict"] == "approved"
    assert payload["checkpoint"]["approval_state"] == "approved"
    assert payload["work_ticket"]["status"] == "approved"
    assert quality_payload["evidence_artifact"]["artifact_id"] in payload["approval_gate"]["evidence_refs"]
    event_types = [event["event_type"] for event in payload["run_trace"]["events"]]
    assert "review_decision_recorded" in event_types


def test_feishu_card_review_callback_maps_to_existing_review_decision_flow() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    quality_response = client.post(
        "/api/v1/quality/evaluate",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "verdict": "go",
            "summary": "证据齐全，可以进入 CEO review。",
            "evidence_points": ["checkpoint exists", "quality evidence attached"],
        },
    )
    quality_payload = quality_response.json()

    response = client.post(
        "/api/v1/approvals/feishu-card-review-decision",
        json={
            "payload": {
                "action": {
                    "value": {
                        "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
                        "decision": "approved",
                        "summary": "来自 Feishu card 的批准。",
                    }
                },
                "operator": {
                    "operator_id": {
                        "open_id": "ou-feishu-reviewer",
                    }
                },
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["toast"]["type"] == "success"
    assert payload["result"]["approval_gate"]["status"] == "approved"
    assert payload["result"]["decision_record"]["created_by"] == "ou-feishu-reviewer"
    assert quality_payload["evidence_artifact"]["artifact_id"] in payload["result"]["approval_gate"]["evidence_refs"]


def test_feishu_card_review_callback_accepts_raw_feishu_style_payload() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    quality_response = client.post(
        "/api/v1/quality/evaluate",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "verdict": "go",
            "summary": "证据齐全，可以进入 CEO review。",
            "evidence_points": ["checkpoint exists", "quality evidence attached"],
        },
    )
    quality_payload = quality_response.json()

    response = client.post(
        "/api/v1/approvals/feishu-card-review-decision",
        json={
            "action": {
                "value": {
                    "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
                    "decision": "approved",
                    "summary": "来自 Feishu 原始 callback 的批准。",
                }
            },
            "operator": {
                "operator_id": {
                    "open_id": "ou-feishu-raw-reviewer",
                }
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["toast"]["type"] == "success"
    assert payload["result"]["approval_gate"]["status"] == "approved"
    assert payload["result"]["decision_record"]["created_by"] == "ou-feishu-raw-reviewer"
    assert quality_payload["evidence_artifact"]["artifact_id"] in payload["result"]["approval_gate"]["evidence_refs"]


def test_override_recovery_creates_override_decision_and_restores_checkpoint() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

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
    payload = override_response.json()
    assert payload["override_decision"]["rollback_ref"] == intake_payload["checkpoint"]["checkpoint_id"]
    assert payload["work_ticket"]["status"] == "override_restored"
    assert payload["task_graph"]["status"] == "ready"
    assert payload["checkpoint"]["superseded_by"] == payload["override_decision"]["decision_id"]
    supersede_refs = set(payload["override_decision"]["supersede_refs"])
    assert f"thread:{intake_payload['work_ticket']['thread_ref']}" in supersede_refs
    assert f"checkpoint:{intake_payload['checkpoint']['checkpoint_id']}" in supersede_refs
    assert f"runtrace:{intake_payload['run_trace']['runtrace_id']}" in supersede_refs
    assert f"taskgraph:{intake_payload['task_graph']['taskgraph_id']}" in supersede_refs
    assert any(ref.startswith("artifact:ea-") for ref in supersede_refs)
    assert "override_decision_recorded" in [event["event_type"] for event in payload["run_trace"]["events"]]


def test_escalation_creates_summary_and_marks_ticket_escalated() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={
            "intent": "让工程帮我做这个小任务，先出一个技术方案",
            "checkpoint_requested": True,
        },
    )
    intake_payload = intake_response.json()

    escalation_response = client.post(
        "/api/v1/governance/escalate",
        json={
            "work_ticket_id": intake_payload["work_ticket"]["ticket_id"],
            "reason": "技术方案与交付时间存在冲突",
            "conflict_points": ["scope too large", "deadline too short"],
            "risk_notes": ["可能影响本周承诺"],
            "suggested_actions": ["缩小范围", "重新排期"],
        },
    )

    assert escalation_response.status_code == 200
    payload = escalation_response.json()
    assert payload["escalation_summary"]["reason"] == "技术方案与交付时间存在冲突"
    assert payload["work_ticket"]["status"] == "escalated"
    assert payload["run_trace"]["status"] == "escalated"
    assert payload["task_graph"]["status"] == "escalated"
    assert "escalation_recorded" in [event["event_type"] for event in payload["run_trace"]["events"]]
