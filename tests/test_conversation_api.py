from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_dashboard_conversation_intake_links_thread_ticket_and_trace() -> None:
    response = client.post(
        "/api/v1/conversations/intake",
        json={
            "surface": "dashboard",
            "channel_id": "dashboard:ceo",
            "participant_ids": ["ceo"],
            "command": {
                "intent": "做一个 AI 产品 MVP，给我一套完整方案",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    thread = payload["thread"]
    command_result = payload["command_result"]

    assert thread["surface"] == "dashboard"
    assert thread["work_ticket_ref"] == command_result["work_ticket"]["ticket_id"]
    assert thread["runtrace_ref"] == command_result["run_trace"]["runtrace_id"]
    assert command_result["work_ticket"]["thread_ref"] == thread["thread_id"]
    assert command_result["run_trace"]["surface"] == "dashboard"
    assert command_result["run_trace"]["thread_ref"] == thread["thread_id"]


def test_feishu_dm_conversation_intake_routes_into_single_department_flow() -> None:
    response = client.post(
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

    assert response.status_code == 200
    payload = response.json()
    thread = payload["thread"]
    command_result = payload["command_result"]

    assert thread["surface"] == "feishu_dm"
    assert thread["interaction_mode"] == "department_task"
    assert command_result["run_trace"]["surface"] == "feishu_dm"
    assert command_result["run_trace"]["channel_ref"] == "feishu:dm:engineering"
    assert command_result["work_ticket"]["thread_ref"] == thread["thread_id"]
    assert command_result["task_graph"]["nodes"][0]["owner_department"] == "Engineering"
    assert "Engineering" in command_result["run_trace"]["visible_speakers"]


def test_conversation_bindings_endpoints_expose_default_dashboard_and_feishu_setup() -> None:
    channel_bindings_response = client.get("/api/v1/conversations/channel-bindings")
    bot_bindings_response = client.get("/api/v1/conversations/bot-seat-bindings")
    room_policies_response = client.get("/api/v1/conversations/room-policies")

    assert channel_bindings_response.status_code == 200
    assert bot_bindings_response.status_code == 200
    assert room_policies_response.status_code == 200

    surfaces = {binding["surface"] for binding in channel_bindings_response.json()}
    assert surfaces == {"dashboard", "feishu_dm", "feishu_group"}
    assert len(bot_bindings_response.json()) == 7
    room_policy_ids = {policy["room_policy_id"] for policy in room_policies_response.json()}
    assert room_policy_ids == {
        "room-executive",
        "room-project",
        "room-launch",
        "room-ops",
        "room-support",
        "room-review",
    }


def test_conversation_channel_binding_and_room_policy_are_editable() -> None:
    update_channel_response = client.put(
        "/api/v1/conversations/channel-bindings/channel-feishu-group",
        json={
            "default_route": "visible_room_orchestrator",
            "mention_policy": "mentioned_agents_only",
            "sync_back_policy": "dashboard_and_visible_room",
            "room_policy_ref": "room-project",
        },
    )
    update_room_response = client.put(
        "/api/v1/conversations/room-policies/room-project",
        json={
            "speaker_mode": "mention_fan_out_visible",
            "visible_participants": ["dashboard-mirror", "ceo-visible-room", "project-room"],
            "turn_taking_rule": "mentioned_agents_reply_in_visible_turns",
            "escalation_rule": "chief_of_staff_or_quality_escalates_to_dashboard",
        },
    )

    assert update_channel_response.status_code == 200
    assert update_room_response.status_code == 200
    assert update_channel_response.json()["default_route"] == "visible_room_orchestrator"
    assert update_room_response.json()["visible_participants"][-1] == "project-room"
