from fastapi.testclient import TestClient

from app.main import app
from app.openclaw.models import OpenClawChatResult

client = TestClient(app)


def test_runtime_executes_formal_project_task_graph_and_completes_trace(monkeypatch) -> None:
    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} formal project output",
                strategy="test_gateway",
                session_key=f"agent:{employee_id}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    execute_response = client.post(
        f"/api/v1/runtime/work-tickets/{intake_payload['work_ticket']['ticket_id']}/execute"
    )

    assert execute_response.status_code == 200
    payload = execute_response.json()

    assert payload["work_ticket"]["status"] == "execution_completed"
    assert payload["task_graph"]["status"] == "completed"
    assert len(payload["executed_nodes"]) == 6
    assert all(node["status"] == "completed" for node in payload["task_graph"]["nodes"])
    assert payload["run_trace"]["status"] == "completed"
    event_types = [event["event_type"] for event in payload["run_trace"]["events"]]
    assert "runtime_execution_started" in event_types
    assert event_types.count("task_node_started") == 6
    assert event_types.count("task_node_completed") == 6
    assert "runtime_execution_completed" in event_types


def test_runtime_executes_single_department_task_and_updates_conversation_thread(monkeypatch) -> None:
    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} single task output",
                strategy="test_gateway",
                session_key=f"agent:{employee_id}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/conversations/intake",
        json={
            "surface": "feishu_dm",
            "channel_id": "feishu:dm:engineering",
            "participant_ids": ["ceo", "feishu-engineering-bot"],
            "bound_agent_ids": ["engineering-lead"],
            "command": {
                "intent": "让工程帮我做这个小任务，先出一个技术方案",
            },
        },
    )
    intake_payload = intake_response.json()

    execute_response = client.post(
        f"/api/v1/runtime/work-tickets/{intake_payload['command_result']['work_ticket']['ticket_id']}/execute"
    )

    assert execute_response.status_code == 200
    payload = execute_response.json()

    assert payload["work_ticket"]["status"] == "completed"
    assert payload["task_graph"]["status"] == "completed"
    assert payload["executed_nodes"] == [payload["task_graph"]["nodes"][0]["node_id"]]
    assert payload["conversation_thread"]["thread_id"] == intake_payload["thread"]["thread_id"]
    assert payload["conversation_thread"]["status"] == "completed"


def test_runtime_rejects_non_executable_work_ticket() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "我有个想法，先记一下以后再说"},
    )
    ticket_id = intake_response.json()["work_ticket"]["ticket_id"]

    execute_response = client.post(f"/api/v1/runtime/work-tickets/{ticket_id}/execute")

    assert execute_response.status_code == 409
    assert execute_response.json()["detail"] == "This work ticket does not have an executable TaskGraph"


def test_runtime_executes_nodes_via_openclaw_gateway(monkeypatch) -> None:
    captured_employees: list[str] = []

    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            captured_employees.append(kwargs["employee_id"])
            return OpenClawChatResult(
                employee_id=kwargs["employee_id"],
                openclaw_agent_id=f"opc-{kwargs['employee_id']}",
                model_ref="bailian/kimi-k2.5",
                reply_text=f"{kwargs['employee_id']} runtime output",
                strategy="test_gateway",
                session_key=f"agent:{kwargs['employee_id']}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    intake_payload = intake_response.json()

    execute_response = client.post(
        f"/api/v1/runtime/work-tickets/{intake_payload['work_ticket']['ticket_id']}/execute"
    )

    assert execute_response.status_code == 200
    payload = execute_response.json()
    assert len(captured_employees) == 6
    assert payload["node_outputs"]
    assert all("runtime output" in output for output in payload["node_outputs"].values())


def test_runtime_executes_discovery_synthesis_loop(monkeypatch) -> None:
    captured_prompts: dict[str, str] = {}

    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            captured_prompts[kwargs["employee_id"]] = kwargs["user_message"]
            return OpenClawChatResult(
                employee_id=kwargs["employee_id"],
                openclaw_agent_id=f"opc-{kwargs['employee_id']}",
                model_ref=f"openclaw:opc-{kwargs['employee_id']}",
                reply_text=f"{kwargs['employee_id']} discovery output",
                strategy="test_gateway",
                session_key=f"agent:{kwargs['employee_id']}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "研究一下本周 AI 产品趋势，并综合成产品与设计建议"},
    )
    intake_payload = intake_response.json()

    execute_response = client.post(
        f"/api/v1/runtime/work-tickets/{intake_payload['work_ticket']['ticket_id']}/execute"
    )

    assert execute_response.status_code == 200
    payload = execute_response.json()

    assert payload["task_graph"]["workflow_recipe"] == "discovery_synthesis"
    assert payload["work_ticket"]["status"] == "completed"
    assert payload["task_graph"]["status"] == "completed"
    assert len(payload["executed_nodes"]) == 5
    assert payload["run_trace"]["status"] == "completed"
    assert set(captured_prompts) == {
        "chief-of-staff",
        "research-lead",
        "product-lead",
        "design-lead",
    }
    assert any("事实" in prompt and "推断" in prompt and "待确认项" in prompt for prompt in captured_prompts.values())


def test_runtime_executes_launch_growth_loop_with_optional_departments(monkeypatch) -> None:
    captured_prompts: dict[str, str] = {}

    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            captured_prompts[kwargs["employee_id"]] = kwargs["user_message"]
            return OpenClawChatResult(
                employee_id=kwargs["employee_id"],
                openclaw_agent_id=f"opc-{kwargs['employee_id']}",
                model_ref=f"openclaw:opc-{kwargs['employee_id']}",
                reply_text=f"{kwargs['employee_id']} launch output",
                strategy="test_gateway",
                session_key=f"agent:{kwargs['employee_id']}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "产品准备上线，给我增长、支持、合作渠道和合规检查方案"},
    )
    intake_payload = intake_response.json()

    execute_response = client.post(
        f"/api/v1/runtime/work-tickets/{intake_payload['work_ticket']['ticket_id']}/execute"
    )

    assert execute_response.status_code == 200
    payload = execute_response.json()

    assert payload["task_graph"]["workflow_recipe"] == "launch_growth"
    assert payload["work_ticket"]["status"] == "completed"
    assert payload["task_graph"]["status"] == "completed"
    assert len(payload["executed_nodes"]) == 6
    assert payload["run_trace"]["status"] == "completed"
    assert len(payload["memory_records"]) == 5
    assert payload["post_launch_follow_up"]["already_exists"] is False
    assert payload["post_launch_follow_up"]["follow_up_work_ticket"]["status"] == "consulting"
    assert payload["post_launch_follow_up"]["follow_up_work_ticket"]["channel_ref"].startswith("dashboard:post-launch:")
    assert set(captured_prompts) == {
        "chief-of-staff",
        "growth-lead",
        "customer-success-lead",
        "partnerships-lead",
        "trust-compliance-lead",
    }
    assert any(
        "发布目标" in prompt and "支持与反馈闭环" in prompt and "风险与合规" in prompt
        for prompt in captured_prompts.values()
    )
    assert any("post_launch_feedback" in record["tags"] for record in payload["memory_records"])
    event_types = [event["event_type"] for event in payload["run_trace"]["events"]]
    assert "launch_feedback_synced" in event_types

    memory_response = client.get(f"/api/v1/memory/work-tickets/{payload['work_ticket']['ticket_id']}")
    assert memory_response.status_code == 200
    memory_payload = memory_response.json()
    assert any("growth_plan" in record["tags"] for record in memory_payload)
    assert any("support_readiness" in record["tags"] for record in memory_payload)
    assert any("post_launch_feedback" in record["tags"] for record in memory_payload)


def test_runtime_post_launch_summary_lists_launch_tickets_followups_and_feedback(monkeypatch) -> None:
    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            return OpenClawChatResult(
                employee_id=kwargs["employee_id"],
                openclaw_agent_id=f"opc-{kwargs['employee_id']}",
                model_ref=f"openclaw:opc-{kwargs['employee_id']}",
                reply_text=f"{kwargs['employee_id']} launch output",
                strategy="test_gateway",
                session_key=f"agent:{kwargs['employee_id']}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "产品准备上线，给我增长、支持和反馈闭环方案"},
    )
    ticket_id = intake_response.json()["work_ticket"]["ticket_id"]
    execute_response = client.post(f"/api/v1/runtime/work-tickets/{ticket_id}/execute")
    assert execute_response.status_code == 200

    summary_response = client.get("/api/v1/runtime/post-launch/summary")

    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert any(ticket["ticket_id"] == ticket_id for ticket in payload["launch_tickets"])
    assert len(payload["follow_ups"]) >= 1
    assert any("post_launch_feedback" in record["tags"] for record in payload["feedback_memories"])


def test_manual_post_launch_routing_returns_existing_follow_up_when_already_created(monkeypatch) -> None:
    class FakeGatewayAdapter:
        def invoke_agent(self, **kwargs):
            return OpenClawChatResult(
                employee_id=kwargs["employee_id"],
                openclaw_agent_id=f"opc-{kwargs['employee_id']}",
                model_ref=f"openclaw:opc-{kwargs['employee_id']}",
                reply_text=f"{kwargs['employee_id']} launch output",
                strategy="test_gateway",
                session_key=f"agent:{kwargs['employee_id']}:runtime:test",
            )

    monkeypatch.setattr("app.runtime.services.get_openclaw_gateway_adapter", lambda: FakeGatewayAdapter())

    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "产品准备上线，给我增长、支持和反馈闭环方案"},
    )
    ticket_id = intake_response.json()["work_ticket"]["ticket_id"]
    execute_response = client.post(f"/api/v1/runtime/work-tickets/{ticket_id}/execute")
    assert execute_response.status_code == 200

    route_response = client.post(f"/api/v1/runtime/work-tickets/{ticket_id}/route-post-launch-follow-up")

    assert route_response.status_code == 200
    payload = route_response.json()
    assert payload["already_exists"] is True
    assert payload["follow_up_work_ticket"]["ticket_id"] == execute_response.json()["post_launch_follow_up"]["follow_up_work_ticket"]["ticket_id"]
