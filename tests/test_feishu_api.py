from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.conversation.services import get_conversation_service
from app.control_plane.services import get_control_plane_service
from app.feishu.models import FeishuBotAppConfig, FeishuSendMessageRequest, FeishuSendMessageResult
from app.feishu.services import get_feishu_surface_adapter_service
from app.main import app
from app.openclaw.models import (
    OpenClawChatResult,
    OpenClawSemanticHandoffCandidate,
    OpenClawSemanticHandoffResult,
)

client = TestClient(app)


def _bot_app_id(employee_id: str) -> str:
    binding = get_conversation_service().get_bot_binding_by_employee_id(employee_id)
    assert binding is not None
    return binding.feishu_app_id


def test_feishu_url_verification_returns_challenge() -> None:
    response = client.post(
        "/api/v1/feishu/events",
        json={
            "type": "url_verification",
            "challenge": "challenge-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-token"}


def test_feishu_dm_message_creates_thread_and_work_ticket() -> None:
    suffix = uuid4().hex[:8]
    engineering_app_id = _bot_app_id("engineering-lead")
    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": engineering_app_id,
                "event_id": f"evt-dm-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-1"}},
                "message": {
                    "message_id": f"om-dm-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_engineering_{suffix}",
                    "content": "{\"text\":\"让工程帮我做这个小任务，先出一个技术方案\"}",
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["surface"] == "feishu_dm"

    thread = client.get(f"/api/v1/conversations/threads/{payload['thread_id']}").json()
    ticket = client.get(f"/api/v1/control-plane/work-tickets/{payload['work_ticket_id']}").json()

    assert thread["surface"] == "feishu_dm"
    assert thread["channel_id"] == f"feishu:dm:oc_dm_engineering_{suffix}"
    assert "engineering-lead" in thread["bound_agent_ids"]
    assert ticket["thread_ref"] == thread["thread_id"]


def test_feishu_dm_message_with_null_mentions_is_processed(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    product_app_id = _bot_app_id("product-lead")
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: None)
    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": product_app_id,
                "event_id": f"evt-dm-null-mentions-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-dm-null"}},
                "message": {
                    "message_id": f"om-dm-null-mentions-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_product_null_mentions_{suffix}",
                    "mentions": None,
                    "content": "{\"text\":\"先记一个产品方向，后续再展开\"}",
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["surface"] == "feishu_dm"


def test_feishu_duplicate_message_is_ignored(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    product_app_id = _bot_app_id("product-lead")
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: None)
    event_payload = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "app_id": product_app_id,
            "event_id": f"evt-dup-{suffix}",
        },
        "event": {
            "sender": {"sender_id": {"open_id": "ou-user-dup"}},
            "message": {
                "message_id": f"om-dup-{suffix}",
                "message_type": "text",
                "chat_type": "p2p",
                "chat_id": f"oc_dm_product_{suffix}",
                "content": "{\"text\":\"先记一个产品想法\"}",
            },
        },
    }

    first = client.post("/api/v1/feishu/events", json=event_payload)
    second = client.post("/api/v1/feishu/events", json=event_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "processed"
    assert second.json()["status"] == "duplicate"
    assert second.json()["message_id"] == f"om-dup-{suffix}"


def test_feishu_group_message_only_targeted_bot_processes(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_texts: list[str] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} 已收到群聊消息。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("product-lead" if app_id == "cli-product-lead" else "chief-of-staff"),
    )
    dialogue_service = FakeDialogueService()
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: (
            sent_texts.append(request.text),
            FeishuSendMessageResult(
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=f"om-sent-{suffix}",
            ),
        )[1],
    )

    targeted = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-product-lead",
                "event_id": f"evt-group-product-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group"}},
                "message": {
                    "message_id": f"om-group-targeted-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_project_room_{suffix}",
                    "content": "{\"text\":\"@_user_1 帮我看下这个方案\"}",
                    "mentions": [
                        {"id": {"open_id": "ou-random-product-per-app"}, "key": "@_user_1", "name": "Product Lead"},
                    ],
                },
            },
        },
    )
    not_targeted = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-chief-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group"}},
                "message": {
                    "message_id": f"om-group-targeted-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_project_room_{suffix}",
                    "content": "{\"text\":\"@_user_1 帮我看下这个方案\"}",
                    "mentions": [
                        {"id": {"open_id": "ou-random-product-per-app"}, "key": "@_user_1", "name": "Product Lead"},
                    ],
                },
            },
        },
    )

    assert targeted.status_code == 200
    payload = targeted.json()
    assert payload["status"] == "processed"
    assert payload["surface"] == "feishu_group"
    assert payload["reply_sent"] is True
    assert payload["target_agent_ids"] == ["product-lead"]
    assert payload["dispatch_mode"] == "single_agent"
    assert sent_texts == ["product-lead 已收到群聊消息。"]

    thread = client.get(f"/api/v1/conversations/threads/{payload['thread_id']}").json()
    assert thread["surface"] == "feishu_group"
    assert thread["bound_agent_ids"] == ["product-lead"]

    assert not_targeted.status_code == 200
    ignored_payload = not_targeted.json()
    assert ignored_payload["status"] == "ignored"
    assert ignored_payload["reply_sent"] is False

    debug_events = client.get("/api/v1/feishu/group-debug-events").json()
    matching = [event for event in debug_events if event["message_id"] == f"om-group-targeted-{suffix}"]
    assert any(event["processed_status"] == "processed" for event in matching)
    assert any(event["processed_status"] == "ignored_non_targeted" for event in matching)
    assert any(event["match_basis"] == "normalized_display_name" for event in matching if event["processed_status"] == "processed")
    assert any(event["match_basis"] == "no_match" for event in matching if event["processed_status"] == "ignored_non_targeted")


def test_feishu_group_message_multiple_targeted_bots_can_both_process(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_texts: list[str] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} 已参与群聊协作。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: (
            sent_texts.append(f"{request.app_id}:{request.text}"),
            FeishuSendMessageResult(
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=f"om-sent-{request.app_id}-{suffix}",
            ),
        )[1],
    )

    payload = {
        "schema": "2.0",
        "event": {
            "sender": {"sender_id": {"open_id": "ou-user-group-multi"}},
            "message": {
                "message_id": f"om-group-multi-{suffix}",
                "message_type": "text",
                "chat_type": "group",
                "chat_id": f"oc_group_project_room_multi_{suffix}",
                "content": "{\"text\":\"@_user_1 @_user_2 一起看下这个方案\"}",
                "mentions": [
                    {"id": {"open_id": "ou-random-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    {"id": {"open_id": "ou-random-product-per-app"}, "key": "@_user_2", "name": "Product Lead"},
                ],
            },
        },
    }

    chief = client.post(
        "/api/v1/feishu/events",
        json={
            **payload,
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-multi-chief-{suffix}",
            },
        },
    )
    product = client.post(
        "/api/v1/feishu/events",
        json={
            **payload,
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-product-lead",
                "event_id": f"evt-group-multi-product-{suffix}",
            },
        },
    )

    assert chief.status_code == 200
    assert product.status_code == 200
    assert chief.json()["status"] == "processed"
    assert product.json()["status"] == "processed"
    assert chief.json()["work_ticket_id"] != product.json()["work_ticket_id"]
    assert chief.json()["target_agent_ids"] == ["chief-of-staff", "product-lead"]
    assert product.json()["target_agent_ids"] == ["product-lead", "chief-of-staff"]
    assert sent_texts == [
        "cli-chief-of-staff:chief-of-staff 已参与群聊协作。",
        "cli-product-lead:product-lead 已参与群聊协作。",
    ]


def test_feishu_group_message_real_payload_name_aliases_dispatch_to_research_and_design(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_texts: list[str] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "research-lead": FeishuBotAppConfig(
                employee_id="research-lead",
                app_id="cli-research-lead",
                app_secret="secret",
                display_name="OPC - Research Lead",
            ),
            "design-lead": FeishuBotAppConfig(
                employee_id="design-lead",
                app_id="cli-design-lead",
                app_secret="secret",
                display_name="OPC - Design Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} 已处理真实 payload 形态。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("research-lead" if app_id == "cli-research-lead" else "design-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: (
            sent_texts.append(f"{request.app_id}:{request.text}"),
            FeishuSendMessageResult(
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=f"om-sent-{request.app_id}-{suffix}",
            ),
        )[1],
    )

    payload = {
        "schema": "2.0",
        "event": {
            "sender": {"sender_id": {"open_id": "ou-user-group-real-shape"}},
            "message": {
                "message_id": f"om-group-real-shape-{suffix}",
                "message_type": "text",
                "chat_type": "group",
                "chat_id": f"oc_group_real_shape_{suffix}",
                "content": "{\"text\":\"@_user_1 @_user_2 你们两个在吗\"}",
                "mentions": [
                    {"id": {"open_id": "ou-random-research-per-app"}, "key": "@_user_1", "name": "Research Lead"},
                    {"id": {"open_id": "ou-random-design-per-app"}, "key": "@_user_2", "name": "Design Lead"},
                ],
            },
        },
    }

    research = client.post(
        "/api/v1/feishu/events",
        json={
            **payload,
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-research-lead",
                "event_id": f"evt-group-real-shape-research-{suffix}",
            },
        },
    )
    design = client.post(
        "/api/v1/feishu/events",
        json={
            **payload,
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-design-lead",
                "event_id": f"evt-group-real-shape-design-{suffix}",
            },
        },
    )

    assert research.status_code == 200
    assert design.status_code == 200
    assert research.json()["status"] == "processed"
    assert design.json()["status"] == "processed"
    assert research.json()["target_agent_ids"] == ["research-lead", "design-lead"]
    assert design.json()["target_agent_ids"] == ["design-lead", "research-lead"]
    assert sent_texts == [
        "cli-research-lead:research-lead 已处理真实 payload 形态。",
        "cli-design-lead:design-lead 已处理真实 payload 形态。",
    ]


def test_feishu_group_debug_detail_endpoint_returns_raw_mentions(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: None)
    chief_app_id = _bot_app_id("chief-of-staff")
    product_app_id = _bot_app_id("product-lead")

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": chief_app_id,
                "event_id": f"evt-group-debug-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-debug"}},
                "message": {
                    "message_id": f"om-group-debug-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_debug_{suffix}",
                    "content": f'{{"text":"<at user_id=\\"{product_app_id}\\">OPC - Product Lead</at> 帮我看下"}}',
                    "mentions": [
                        {"id": {"user_id": product_app_id}, "name": "OPC - Product Lead"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    debug_event_id = f"{chief_app_id}:om-group-debug-{suffix}"
    detail_response = client.get(f"/api/v1/feishu/group-debug-events/{debug_event_id}")
    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["debug_event_id"] == debug_event_id
    assert payload["processed_status"] == "ignored_non_targeted"
    assert payload["match_basis"] == "no_match"
    assert payload["raw_mentions_summary"]
    assert product_app_id in " ".join(payload["raw_mentions_summary"])


def test_feishu_group_visible_handoff_stays_in_same_thread(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            if employee_id == "chief-of-staff":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text="Chief of Staff 先做 framing，并请 Product Lead 接着补充产品判断。",
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    handoff_targets=["product-lead"],
                    handoff_reason="需要产品判断",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text="Product Lead 接棒补充产品判断。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.thread_ref or "", request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    dialogue_service = FakeDialogueService()
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-handoff-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-handoff"}},
                "message": {
                    "message_id": f"om-group-handoff-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_handoff_{suffix}",
                    "content": '{"text":"@_user_1 帮我组织一下"}',
                    "mentions": [
                        {"id": {"open_id": "ou-random-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["reply_count"] == 3
    assert sent_messages[0][0] == "cli-chief-of-staff"
    assert sent_messages[1][0] == "cli-product-lead"
    assert len(sent_messages) == 3
    assert len({thread_ref for _, thread_ref, _ in sent_messages}) == 1
    thread = client.get(f"/api/v1/conversations/threads/{payload['thread_id']}").json()
    assert "product-lead" in thread["bound_agent_ids"]
    assert thread["visible_room_ref"] == thread["channel_id"]

    run_trace = get_control_plane_service().get_required_run_trace(payload["runtrace_id"])
    handoff_events = [event for event in run_trace.events if event.event_type == "visible_agent_handoff"]
    assert handoff_events
    assert handoff_events[-1].metadata["handoff_source_agent"] == "chief-of-staff"
    assert handoff_events[-1].metadata["handoff_targets"] == "product-lead"


def test_feishu_group_interruption_reuses_thread_and_supersedes_prior_run(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} 收到消息。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.thread_ref or "", request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_bot_config("chief-of-staff"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    chat_id = f"oc_group_interruption_{suffix}"
    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-interrupt-first-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-interruption"}},
                "message": {
                    "message_id": f"om-group-interrupt-first-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": chat_id,
                    "content": '{"text":"@_user_1 先开始数7"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-interrupt-second-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-interruption"}},
                "message": {
                    "message_id": f"om-group-interrupt-second-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": chat_id,
                    "content": '{"text":"@_user_1 等等，刚才那一步不对"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["thread_id"] == second_payload["thread_id"]

    thread = client.get(f"/api/v1/conversations/threads/{first_payload['thread_id']}").json()
    assert thread["active_runtrace_ref"] == second_payload["runtrace_id"]
    assert thread["delivery_guard_epoch"] == 2
    assert first_payload["runtrace_id"] in thread["superseded_runtrace_refs"]

    first_run = client.get(f"/api/v1/control-plane/run-traces/{first_payload['runtrace_id']}").json()
    second_run = client.get(f"/api/v1/control-plane/run-traces/{second_payload['runtrace_id']}").json()
    assert first_run["status"] == "superseded"
    assert first_run["superseded_by_runtrace_ref"] == second_payload["runtrace_id"]
    assert second_run["supersedes_runtrace_ref"] == first_payload["runtrace_id"]
    assert second_run["delivery_guard_epoch"] == 2


def test_feishu_group_source_turn_persists_pending_handoff_state(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    settings = get_settings()
    monkeypatch.setattr(settings, "feishu_visible_handoff_turn_limit", 0)
    sent_messages: list[tuple[str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "quality-lead": FeishuBotAppConfig(
                employee_id="quality-lead",
                app_id="cli-quality-lead",
                app_secret="secret",
                display_name="OPC - Quality Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text="Chief of Staff 继续组织一下。请 Quality Lead 接棒，继续报8。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
                handoff_targets=["quality-lead"],
                handoff_reason="继续报8",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.thread_ref or "", request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-pending-state-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-pending-state-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_bot_config("chief-of-staff"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-pending-state-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-pending-state"}},
                "message": {
                    "message_id": f"om-pending-state-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_pending_state_{suffix}",
                    "content": '{"text":"@_user_1 开始玩逢7过"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["reply_count"] == 1

    thread = client.get(f"/api/v1/conversations/threads/{payload['thread_id']}").json()
    assert thread["pending_handoff"]["source_agent_id"] == "chief-of-staff"
    assert thread["pending_handoff"]["target_agent_id"] == "quality-lead"
    assert thread["pending_handoff"]["instruction"] == "继续报8"
    assert thread["pending_handoff"]["source_runtrace_ref"] == payload["runtrace_id"]
    assert thread["last_committed_state"]["last_speaker"] == "chief-of-staff"
    assert thread["last_committed_state"]["baton_owner"] == "quality-lead"
    assert thread["last_committed_state"]["next_expected_number"] == 8
    assert thread["last_committed_state"]["last_instruction"] == "继续报8"

    run_trace = get_control_plane_service().get_required_run_trace(payload["runtrace_id"])
    assert any(event.event_type == "pending_handoff_captured" for event in run_trace.events)
    assert any(event.event_type == "last_committed_state_updated" for event in run_trace.events)


def test_feishu_group_interruption_dispatch_uses_pending_handoff_state(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    settings = get_settings()
    sent_messages: list[tuple[str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "quality-lead": FeishuBotAppConfig(
                employee_id="quality-lead",
                app_id="cli-quality-lead",
                app_secret="secret",
                display_name="OPC - Quality Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def generate_reply(self, **kwargs):
            self.calls.append(kwargs)
            employee_id = kwargs["employee_id"]
            user_message = kwargs["user_message"]
            turn_mode = kwargs.get("turn_mode", "source")
            if "开始玩逢7过" in user_message:
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text="Chief of Staff 先起头。请 Quality Lead 接棒，继续报8。",
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    handoff_targets=["quality-lead"],
                    handoff_reason="继续报8",
                    turn_mode="source",
                )
            if turn_mode == "handoff_target":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text="Quality Lead 先解释刚才的判断，我会补正这一步。",
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text="Chief of Staff 先暂停旧接棒。请 Quality Lead 解释刚才为什么让下一位继续报8。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
                handoff_targets=["quality-lead"],
                handoff_reason="解释继续报8",
                turn_mode="source",
            )

    dialogue_service = FakeDialogueService()

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.thread_ref or "", request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-interruption-state-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-interruption-state-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "quality-lead"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    monkeypatch.setattr(settings, "feishu_visible_handoff_turn_limit", 0)
    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-interruption-state-first-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-interruption-state"}},
                "message": {
                    "message_id": f"om-interruption-state-first-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_interruption_state_{suffix}",
                    "content": '{"text":"@_user_1 开始玩逢7过"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )
    settings.feishu_visible_handoff_turn_limit = 2
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-interruption-state-second-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-interruption-state"}},
                "message": {
                    "message_id": f"om-interruption-state-second-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_interruption_state_{suffix}",
                    "content": '{"text":"@_user_1 等等，刚才那一步为什么不对？"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["target_agent_ids"] == ["chief-of-staff", "quality-lead"]

    source_context = dialogue_service.calls[1]["collaboration_context"]
    assert source_context is not None
    assert getattr(source_context, "interruption_mode") == "user_interruption"
    assert "quality-lead" in (getattr(source_context, "pending_handoff_summary") or "")
    assert "chief-of-staff" in (getattr(source_context, "pending_handoff_summary") or "")
    assert "next_expected_number" in (getattr(source_context, "last_committed_state_summary") or "")
    assert "8" in (getattr(source_context, "last_committed_state_summary") or "")

    handoff_context = dialogue_service.calls[2]["handoff_context"]
    assert handoff_context is not None
    assert getattr(handoff_context, "interruption_reason") == "user_interruption"
    assert "quality-lead" in (getattr(handoff_context, "pending_handoff_summary") or "")
    assert "8" in (getattr(handoff_context, "last_committed_state_summary") or "")

    inbound_events = client.get("/api/v1/feishu/inbound-events").json()
    second_inbound = next(event for event in inbound_events if event["message_id"] == f"om-interruption-state-second-{suffix}")
    assert second_inbound["interruption_dispatch_targets"] == ["chief-of-staff", "quality-lead"]


def test_feishu_group_interruption_defers_source_turn_to_correction_bot(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    settings = get_settings()
    sent_messages: list[tuple[str, str, str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "quality-lead": FeishuBotAppConfig(
                employee_id="quality-lead",
                app_id="cli-quality-lead",
                app_secret="secret",
                display_name="OPC - Quality Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def generate_reply(self, **kwargs):
            self.calls.append(kwargs)
            employee_id = kwargs["employee_id"]
            user_message = kwargs["user_message"]
            turn_mode = kwargs.get("turn_mode", "source")
            if "开始玩逢7过" in user_message:
                if turn_mode == "source":
                    return OpenClawChatResult(
                        employee_id=employee_id,
                        openclaw_agent_id=f"opc-{employee_id}",
                        model_ref=f"openclaw:opc-{employee_id}",
                        reply_text="Chief of Staff 先起头。请 Quality Lead 判断这一步。",
                        strategy="openclaw_native_gateway",
                        session_key=f"agent:opc-{employee_id}:feishu:group:test",
                        handoff_targets=["quality-lead"],
                        handoff_reason="判断是否该继续报8",
                        turn_mode="source",
                    )
                if employee_id == "quality-lead":
                    return OpenClawChatResult(
                        employee_id=employee_id,
                        openclaw_agent_id="opc-quality-lead",
                        model_ref="openclaw:opc-quality-lead",
                        reply_text="Quality Lead 判断后交还给 Chief of Staff，继续报8。",
                        strategy="openclaw_native_gateway",
                        session_key="agent:opc-quality-lead:feishu:group:test",
                        handoff_targets=["chief-of-staff"],
                        handoff_reason="继续报8",
                        turn_mode="handoff_target",
                    )
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 继续报8。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    turn_mode="handoff_target",
                )
            if "quality lead 刚才为什么让 chief-of-staff 继续报8" in user_message:
                if turn_mode == "source":
                    raise AssertionError("interruption run should defer the source turn to quality-lead")
                if employee_id == "quality-lead":
                    return OpenClawChatResult(
                        employee_id=employee_id,
                        openclaw_agent_id="opc-quality-lead",
                        model_ref="openclaw:opc-quality-lead",
                        reply_text="Quality Lead 抱歉，我刚才判断错了，应该先纠正这一步。",
                        strategy="openclaw_native_gateway",
                        session_key="agent:opc-quality-lead:feishu:group:test",
                        turn_mode="handoff_target",
                    )
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 收到更正，现在继续报8。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    turn_mode="handoff_target",
                )
            raise AssertionError(f"unexpected test input: {user_message}")

    dialogue_service = FakeDialogueService()

    def fake_send(self, request):
        sent_messages.append(
            (
                request.app_id,
                request.source_kind,
                request.thread_ref or "",
                request.runtrace_ref or "",
                request.text,
            )
        )
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-interruption-order-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-interruption-order-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "quality-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    monkeypatch.setattr(settings, "feishu_visible_handoff_turn_limit", 2)
    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-interruption-order-first-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-interruption-order"}},
                "message": {
                    "message_id": f"om-interruption-order-first-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_interruption_order_{suffix}",
                    "content": '{"text":"@_user_1 开始玩逢7过"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )
    settings.feishu_visible_handoff_turn_limit = 4
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-interruption-order-second-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-interruption-order"}},
                "message": {
                    "message_id": f"om-interruption-order-second-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_interruption_order_{suffix}",
                    "content": '{"text":"@_user_1 等等，quality lead 刚才为什么让 chief-of-staff 继续报8？"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["target_agent_ids"] == ["quality-lead", "chief-of-staff"]

    interruption_calls = [
        call
        for call in dialogue_service.calls
        if "quality lead 刚才为什么让 chief-of-staff 继续报8" in call["user_message"]
    ]
    assert [call.get("turn_mode", "source") for call in interruption_calls] == ["handoff_target", "handoff_target"]
    assert [call["employee_id"] for call in interruption_calls] == ["quality-lead", "chief-of-staff"]

    second_thread_id = second.json()["thread_id"]
    second_runtrace_id = second.json()["runtrace_id"]
    second_run_messages = [
        (app_id, source_kind, text)
        for app_id, source_kind, thread_ref, runtrace_ref, text in sent_messages
        if thread_ref == second_thread_id
        and runtrace_ref == second_runtrace_id
        and source_kind != "visible_handoff_notice"
    ]
    assert [app_id for app_id, _, _ in second_run_messages] == ["cli-quality-lead", "cli-chief-of-staff"]
    assert second_run_messages[0][2].startswith("Quality Lead 抱歉")
    assert "继续报8" in second_run_messages[1][2]


def test_feishu_group_interruption_orders_additional_targets_by_message_appearance(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    settings = get_settings()
    sent_messages: list[tuple[str, str, str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "quality-lead": FeishuBotAppConfig(
                employee_id="quality-lead",
                app_id="cli-quality-lead",
                app_secret="secret",
                display_name="OPC - Quality Lead",
            ),
            "design-lead": FeishuBotAppConfig(
                employee_id="design-lead",
                app_id="cli-design-lead",
                app_secret="secret",
                display_name="OPC - Design Lead",
            ),
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def generate_reply(self, **kwargs):
            self.calls.append(kwargs)
            employee_id = kwargs["employee_id"]
            user_message = kwargs["user_message"]
            turn_mode = kwargs.get("turn_mode", "source")
            if "开始玩逢7过" in user_message:
                if turn_mode == "source":
                    return OpenClawChatResult(
                        employee_id=employee_id,
                        openclaw_agent_id=f"opc-{employee_id}",
                        model_ref=f"openclaw:opc-{employee_id}",
                        reply_text="Chief of Staff 先起头。请 Quality Lead 判断这一步。",
                        strategy="openclaw_native_gateway",
                        session_key=f"agent:opc-{employee_id}:feishu:group:test",
                        handoff_targets=["quality-lead"],
                        handoff_reason="判断是否该继续报8",
                        turn_mode="source",
                    )
                if employee_id == "quality-lead":
                    return OpenClawChatResult(
                        employee_id=employee_id,
                        openclaw_agent_id="opc-quality-lead",
                        model_ref="openclaw:opc-quality-lead",
                        reply_text="Quality Lead 判断后交还给 Chief of Staff，继续报8。",
                        strategy="openclaw_native_gateway",
                        session_key="agent:opc-quality-lead:feishu:group:test",
                        handoff_targets=["chief-of-staff"],
                        handoff_reason="继续报8",
                        turn_mode="handoff_target",
                    )
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text=f"{employee_id} 完成这一轮回复。",
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    turn_mode="handoff_target",
                )
            if "design lead 你先补充一下" in user_message:
                if turn_mode == "source":
                    raise AssertionError("interruption run should still defer the source turn to quality-lead")
                reply_map = {
                    "quality-lead": "Quality Lead 先纠正刚才的判断，这一步先澄清。",
                    "chief-of-staff": "Chief of Staff 收到更正，现在继续报8。",
                    "design-lead": "Design Lead 先补充为什么这一步体验上会让人困惑。",
                    "product-lead": "Product Lead 再补充这一步规则表达应该怎么改。",
                }
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text=reply_map[employee_id],
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    turn_mode="handoff_target",
                )
            raise AssertionError(f"unexpected test input: {user_message}")

    dialogue_service = FakeDialogueService()

    def fake_send(self, request):
        sent_messages.append(
            (
                request.app_id,
                request.source_kind,
                request.thread_ref or "",
                request.runtrace_ref or "",
                request.text,
            )
        )
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-interruption-extra-order-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-interruption-extra-order-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: next(
            config
            for config in [
                fake_bot_config("chief-of-staff"),
                fake_bot_config("quality-lead"),
                fake_bot_config("design-lead"),
                fake_bot_config("product-lead"),
            ]
            if config and config.app_id == app_id
        ),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    monkeypatch.setattr(settings, "feishu_visible_handoff_turn_limit", 2)
    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-interruption-extra-order-first-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-interruption-extra-order"}},
                "message": {
                    "message_id": f"om-interruption-extra-order-first-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_interruption_extra_order_{suffix}",
                    "content": '{"text":"@_user_1 开始玩逢7过"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )
    settings.feishu_visible_handoff_turn_limit = 4
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-interruption-extra-order-second-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-interruption-extra-order"}},
                "message": {
                    "message_id": f"om-interruption-extra-order-second-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_interruption_extra_order_{suffix}",
                    "content": '{"text":"@_user_1 等等，quality lead 刚才为什么让 chief-of-staff 继续报8？design lead 你先补充一下，product lead 再补充。"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["target_agent_ids"] == ["quality-lead", "chief-of-staff", "design-lead", "product-lead"]

    second_thread_id = second.json()["thread_id"]
    second_runtrace_id = second.json()["runtrace_id"]
    second_run_messages = [
        (app_id, source_kind, text)
        for app_id, source_kind, thread_ref, runtrace_ref, text in sent_messages
        if thread_ref == second_thread_id
        and runtrace_ref == second_runtrace_id
        and source_kind != "visible_handoff_notice"
    ]
    assert [app_id for app_id, _, _ in second_run_messages] == [
        "cli-quality-lead",
        "cli-chief-of-staff",
        "cli-design-lead",
        "cli-product-lead",
    ]


def test_feishu_group_plain_text_target_forces_visible_handoff(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            if employee_id == "chief-of-staff":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="收到，我先做一下组织，并请 Product Lead 接着补充产品判断。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id="opc-product-lead",
                model_ref="openclaw:opc-product-lead",
                reply_text="Product Lead 接棒补充产品判断。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-product-lead:feishu:group:test",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.thread_ref or "", request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    dialogue_service = FakeDialogueService()
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-plain-handoff-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-plain-handoff"}},
                "message": {
                    "message_id": f"om-group-plain-handoff-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_plain_handoff_{suffix}",
                    "content": '{"text":"@_user_1 你可以给product lead发送一条消息并让这个bot回复吗"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["target_agent_ids"] == ["chief-of-staff", "product-lead"]
    assert payload["reply_count"] == 2
    assert sent_messages[0][0] == "cli-chief-of-staff"
    assert sent_messages[1][0] == "cli-product-lead"
    assert len(sent_messages) == 2
    assert len({thread_ref for _, thread_ref, _ in sent_messages}) == 1

    inbound_events = client.get("/api/v1/feishu/inbound-events").json()
    inbound = next(event for event in inbound_events if event["message_id"] == f"om-group-plain-handoff-{suffix}")
    assert inbound["deterministic_text_target_ids"] == ["product-lead"]
    assert inbound["forced_handoff_targets"] == ["product-lead"]

    debug_event_id = f"cli-chief-of-staff:om-group-plain-handoff-{suffix}"
    debug_payload = client.get(f"/api/v1/feishu/group-debug-events/{debug_event_id}").json()
    assert debug_payload["target_resolution_basis"] == "deterministic_text"
    assert debug_payload["deterministic_text_target_ids"] == ["product-lead"]

    run_trace = get_control_plane_service().get_required_run_trace(payload["runtrace_id"])
    assert run_trace.handoff_origin == "deterministic_text"
    handoff_events = [event for event in run_trace.events if event.event_type == "visible_agent_handoff"]
    assert handoff_events
    assert handoff_events[-1].metadata["handoff_origin"] == "deterministic_text"


def test_feishu_group_semantic_handoff_can_route_to_product_lead(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief-of-staff",
                app_secret="secret",
                display_name="OPC - Chief of Staff",
            ),
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            if employee_id == "chief-of-staff":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="收到，我先做框定，并请 Product Lead 接着从产品视角判断。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id="opc-product-lead",
                model_ref="openclaw:opc-product-lead",
                reply_text="Product Lead 认为这个需求值得做。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-product-lead:feishu:group:test",
            )

        def infer_visible_handoff_targets(self, **kwargs):
            from app.openclaw.models import OpenClawSemanticHandoffCandidate, OpenClawSemanticHandoffResult

            return OpenClawSemanticHandoffResult(
                needs_handoff=True,
                targets=[
                    OpenClawSemanticHandoffCandidate(
                        employee_id="product-lead",
                        confidence=0.92,
                        reason="用户明确要求产品判断",
                    )
                ],
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.thread_ref or "", request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-semantic-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-semantic-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-semantic-handoff-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-semantic"}},
                "message": {
                    "message_id": f"om-group-semantic-handoff-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_semantic_handoff_{suffix}",
                    "content": '{"text":"@_user_1 需要产品来判断这个需求是否值得做"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["reply_count"] == 2
    assert sent_messages[0][0] == "cli-chief-of-staff"
    assert sent_messages[1][0] == "cli-product-lead"

    inbound_events = client.get("/api/v1/feishu/inbound-events").json()
    inbound = next(event for event in inbound_events if event["message_id"] == f"om-group-semantic-handoff-{suffix}")
    assert inbound["semantic_handoff_target_ids"] == ["product-lead"]
    assert inbound["forced_handoff_targets"] == ["product-lead"]

    debug_event_id = f"cli-chief-of-staff:om-group-semantic-handoff-{suffix}"
    debug_payload = client.get(f"/api/v1/feishu/group-debug-events/{debug_event_id}").json()
    assert debug_payload["target_resolution_basis"] == "semantic_llm"
    assert debug_payload["semantic_handoff_target_ids"] == ["product-lead"]
    assert debug_payload["semantic_handoff_candidates"][0]["employee_id"] == "product-lead"


def test_feishu_group_plain_text_bot_name_can_dispatch_without_at(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-lead",
                app_secret="secret",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            return OpenClawChatResult(
                employee_id="product-lead",
                openclaw_agent_id="opc-product-lead",
                model_ref="openclaw:opc-product-lead",
                reply_text="Product Lead 已收到，会从产品视角继续。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-product-lead:feishu:group:test",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-plain-name-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-plain-name-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_bot_config("product-lead"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-product-lead",
                "event_id": f"evt-group-plain-name-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-plain-name"}},
                "message": {
                    "message_id": f"om-group-plain-name-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_plain_name_{suffix}",
                    "content": '{"text":"Product Lead 帮我看下这个需求值不值得做"}',
                    "mentions": [],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["target_agent_ids"] == ["product-lead"]
    assert sent_messages[0][0] == "cli-product-lead"

    inbound_events = client.get("/api/v1/feishu/inbound-events").json()
    inbound = next(event for event in inbound_events if event["message_id"] == f"om-group-plain-name-{suffix}")
    assert inbound["target_agent_ids"] == ["product-lead"]
    assert inbound["deterministic_name_target_ids"] == ["product-lead"]

    debug_event_id = f"cli-product-lead:om-group-plain-name-{suffix}"
    debug_payload = client.get(f"/api/v1/feishu/group-debug-events/{debug_event_id}").json()
    assert debug_payload["dispatch_resolution_basis"] == "deterministic_name"
    assert debug_payload["deterministic_name_target_ids"] == ["product-lead"]


def test_feishu_group_project_lead_can_force_design_handoff(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "delivery-lead": FeishuBotAppConfig(
                employee_id="delivery-lead",
                app_id="cli-project-lead",
                app_secret="secret",
                display_name="OPC - Project Lead",
            ),
            "design-lead": FeishuBotAppConfig(
                employee_id="design-lead",
                app_id="cli-design-lead",
                app_secret="secret",
                display_name="OPC - Design Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            text = (
                "Project Lead 先做项目 framing，并请 Design Lead 接着补充设计判断。"
                if employee_id == "delivery-lead"
                else "Design Lead 接棒补充设计判断。"
            )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=text,
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-project-design-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-project-design-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("delivery-lead" if app_id == "cli-project-lead" else "design-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-project-lead",
                "event_id": f"evt-group-project-design-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-project-design"}},
                "message": {
                    "message_id": f"om-group-project-design-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_project_design_{suffix}",
                    "content": '{"text":"@_user_1 你可以给design lead发送一条消息并让这个bot回复吗"}',
                    "mentions": [
                        {"id": {"open_id": "ou-project-per-app"}, "key": "@_user_1", "name": "Project Lead"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "processed"
    assert payload["target_agent_ids"] == ["delivery-lead", "design-lead"]
    assert sent_messages[0][0] == "cli-project-lead"
    assert sent_messages[1][0] == "cli-design-lead"

    inbound_events = client.get("/api/v1/feishu/inbound-events").json()
    inbound = next(event for event in inbound_events if event["message_id"] == f"om-group-project-design-{suffix}")
    assert inbound["deterministic_text_target_ids"] == ["design-lead"]


def test_feishu_handoff_target_turn_retries_when_reply_repeats_source(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "delivery-lead": FeishuBotAppConfig(
                employee_id="delivery-lead",
                app_id="cli-project-lead",
                app_secret="secret",
                display_name="OPC - Project Lead",
            ),
            "design-lead": FeishuBotAppConfig(
                employee_id="design-lead",
                app_id="cli-design-lead",
                app_secret="secret",
                display_name="OPC - Design Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def generate_reply(self, **kwargs):
            self.calls.append(kwargs)
            employee_id = kwargs["employee_id"]
            turn_mode = kwargs.get("turn_mode", "source")
            handoff_context = kwargs.get("handoff_context")
            if employee_id == "delivery-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text="收到。Project Lead 先做当前问题的组织和 framing，并请 Design Lead 在同一群里接棒补充。",
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    handoff_targets=["design-lead"],
                    turn_mode="source",
                )
            if turn_mode == "handoff_target" and handoff_context is not None and getattr(handoff_context, "retry_reason", None):
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id=f"opc-{employee_id}",
                    model_ref=f"openclaw:opc-{employee_id}",
                    reply_text="Design Lead 从体验结构补充：先确认用户路径、信息层级和关键交互，再继续展开设计方案。",
                    strategy="openclaw_native_gateway",
                    session_key=f"agent:opc-{employee_id}:feishu:group:test",
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text="收到。Project Lead 先做当前问题的组织和 framing，并请 Design Lead 在同一群里接棒补充。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
                turn_mode="handoff_target",
            )

    dialogue_service = FakeDialogueService()

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-project-design-retry-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-project-design-retry-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("delivery-lead" if app_id == "cli-project-lead" else "design-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-project-lead",
                "event_id": f"evt-group-project-design-retry-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-project-design-retry"}},
                "message": {
                    "message_id": f"om-group-project-design-retry-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_project_design_retry_{suffix}",
                    "content": '{"text":"@_user_1 你可以给design lead发送一条消息并让这个bot回复吗"}',
                    "mentions": [
                        {"id": {"open_id": "ou-project-per-app"}, "key": "@_user_1", "name": "Project Lead"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    assert sent_messages[0][0] == "cli-project-lead"
    assert sent_messages[1][0] == "cli-design-lead"
    assert sent_messages[0][1] != sent_messages[1][1]
    assert "体验结构" in sent_messages[1][1]
    assert dialogue_service.calls[1]["turn_mode"] == "handoff_target"
    assert getattr(dialogue_service.calls[1]["handoff_context"], "handoff_source_agent") == "delivery-lead"
    assert getattr(dialogue_service.calls[2]["handoff_context"], "retry_reason") == "avoid_repeating_source_framing"

    run_trace = get_control_plane_service().get_required_run_trace(response.json()["runtrace_id"])
    assert run_trace.handoff_repetition_violation is True


def test_feishu_visible_handoff_can_chain_beyond_two_turns_and_stop_at_limit(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    settings = get_settings()
    monkeypatch.setattr(settings, "feishu_visible_handoff_turn_limit", 3)
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(employee_id="chief-of-staff", app_id="cli-chief-of-staff", app_secret="secret", display_name="OPC - Chief of Staff"),
            "product-lead": FeishuBotAppConfig(employee_id="product-lead", app_id="cli-product-lead", app_secret="secret", display_name="OPC - Product Lead"),
            "design-lead": FeishuBotAppConfig(employee_id="design-lead", app_id="cli-design-lead", app_secret="secret", display_name="OPC - Design Lead"),
            "research-lead": FeishuBotAppConfig(employee_id="research-lead", app_id="cli-research-lead", app_secret="secret", display_name="OPC - Research Lead"),
            "engineering-lead": FeishuBotAppConfig(employee_id="engineering-lead", app_id="cli-engineering-lead", app_secret="secret", display_name="OPC - Engineering Lead"),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            if employee_id == "chief-of-staff":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 先做组织，然后请 Product Lead 接棒。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    handoff_targets=["product-lead"],
                    turn_mode="source",
                )
            if employee_id == "product-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-product-lead",
                    model_ref="openclaw:opc-product-lead",
                    reply_text="Product Lead 给出产品判断，并请 Design Lead 接棒。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-product-lead:feishu:group:test",
                    handoff_targets=["design-lead"],
                    handoff_reason="需要设计补充体验方案",
                    turn_mode="handoff_target",
                )
            if employee_id == "design-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-design-lead",
                    model_ref="openclaw:opc-design-lead",
                    reply_text="Design Lead 补充体验方案，并请 Research Lead 接棒。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-design-lead:feishu:group:test",
                    handoff_targets=["research-lead"],
                    handoff_reason="需要研究验证外部信号",
                    turn_mode="handoff_target",
                )
            if employee_id == "research-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-research-lead",
                    model_ref="openclaw:opc-research-lead",
                    reply_text="Research Lead 补充研究信号，并请 Engineering Lead 接棒。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-research-lead:feishu:group:test",
                    handoff_targets=["engineering-lead"],
                    handoff_reason="需要工程确认实现约束",
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text="Engineering Lead 不应在本次 turn limit 下出现。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
                turn_mode="handoff_target",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-chain-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-chain-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: next(config for config in [fake_bot_config("chief-of-staff"), fake_bot_config("product-lead"), fake_bot_config("design-lead"), fake_bot_config("research-lead"), fake_bot_config("engineering-lead")] if config and config.app_id == app_id))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-chain-limit-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-chain-limit"}},
                "message": {
                    "message_id": f"om-group-chain-limit-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_chain_limit_{suffix}",
                    "content": '{"text":"@_user_1 帮我组织一下并持续接棒"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    assert [app_id for app_id, _ in sent_messages] == [
        "cli-chief-of-staff",
        "cli-product-lead",
        "cli-design-lead",
    ]
    run_trace = get_control_plane_service().get_required_run_trace(response.json()["runtrace_id"])
    assert run_trace.stopped_by_turn_limit is True
    assert run_trace.visible_turn_count == 3
    assert run_trace.remaining_turn_budget == 0
    assert run_trace.stop_reason == "limit_reached"
    assert sum(1 for event in run_trace.events if event.event_type == "visible_agent_handoff") == 2


def test_feishu_visible_handoff_can_continue_from_reply_text_named_bot_without_handoff_line(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(employee_id="chief-of-staff", app_id="cli-chief-of-staff", app_secret="secret", display_name="OPC - Chief of Staff"),
            "product-lead": FeishuBotAppConfig(employee_id="product-lead", app_id="cli-product-lead", app_secret="secret", display_name="OPC - Product Lead"),
            "design-lead": FeishuBotAppConfig(employee_id="design-lead", app_id="cli-design-lead", app_secret="secret", display_name="OPC - Design Lead"),
            "research-lead": FeishuBotAppConfig(employee_id="research-lead", app_id="cli-research-lead", app_secret="secret", display_name="OPC - Research Lead"),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            if employee_id == "chief-of-staff":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 先做组织，然后请 Product Lead 接棒。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    handoff_targets=["product-lead"],
                    turn_mode="source",
                )
            if employee_id == "product-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-product-lead",
                    model_ref="openclaw:opc-product-lead",
                    reply_text="Product Lead 给出产品判断，并请 Design Lead 接棒。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-product-lead:feishu:group:test",
                    handoff_targets=["design-lead"],
                    turn_mode="handoff_target",
                )
            if employee_id == "design-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-design-lead",
                    model_ref="openclaw:opc-design-lead",
                    reply_text="Design Lead 补充体验判断。下一位由 Research Lead 回复。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-design-lead:feishu:group:test",
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id="opc-research-lead",
                model_ref="openclaw:opc-research-lead",
                reply_text="Research Lead 补充研究信号。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-research-lead:feishu:group:test",
                turn_mode="handoff_target",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-chain-reply-name-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-chain-reply-name-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: next(config for config in [fake_bot_config("chief-of-staff"), fake_bot_config("product-lead"), fake_bot_config("design-lead"), fake_bot_config("research-lead")] if config and config.app_id == app_id),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-reply-name-chain-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-reply-name-chain"}},
                "message": {
                    "message_id": f"om-group-reply-name-chain-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_reply_name_chain_{suffix}",
                    "content": '{"text":"@_user_1 帮我组织并持续接棒"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    assert [app_id for app_id, _ in sent_messages] == [
        "cli-chief-of-staff",
        "cli-product-lead",
        "cli-design-lead",
        "cli-research-lead",
    ]

    run_trace = get_control_plane_service().get_required_run_trace(response.json()["runtrace_id"])
    handoff_events = [event for event in run_trace.events if event.event_type == "visible_agent_handoff"]
    assert len(handoff_events) == 3
    assert handoff_events[-1].metadata["handoff_targets"] == "research-lead"


def test_feishu_visible_handoff_allows_same_bot_to_reply_again_when_user_explicitly_requests_it(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(employee_id="chief-of-staff", app_id="cli-chief-of-staff", app_secret="secret", display_name="OPC - Chief of Staff"),
            "product-lead": FeishuBotAppConfig(employee_id="product-lead", app_id="cli-product-lead", app_secret="secret", display_name="OPC - Product Lead"),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def __init__(self) -> None:
            self.chief_turns = 0

        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            if employee_id == "chief-of-staff":
                self.chief_turns += 1
                if self.chief_turns == 1:
                    return OpenClawChatResult(
                        employee_id=employee_id,
                        openclaw_agent_id="opc-chief-of-staff",
                        model_ref="openclaw:opc-chief-of-staff",
                        reply_text="Chief of Staff 先做组织，并请 Product Lead 接着补充产品判断。",
                        strategy="openclaw_native_gateway",
                        session_key="agent:opc-chief-of-staff:feishu:group:test",
                        handoff_targets=["product-lead"],
                        turn_mode="source",
                    )
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 做最终总结：先按产品判断推进，再把关键结论收敛成可执行项。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id="opc-product-lead",
                model_ref="openclaw:opc-product-lead",
                reply_text="Product Lead 补充产品判断，并给出产品建议。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-product-lead:feishu:group:test",
                turn_mode="handoff_target",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-repeat-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-repeat-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    dialogue_service = FakeDialogueService()
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: dialogue_service)
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-repeat-chief-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-repeat-chief"}},
                "message": {
                    "message_id": f"om-group-repeat-chief-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_repeat_chief_{suffix}",
                    "content": '{"text":"@_user_1 先组织一下，再让 Product Lead 补充，最后请你再总结"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    sent_app_ids = [app_id for app_id, _ in sent_messages]
    assert sent_app_ids[0] == "cli-chief-of-staff"
    assert sent_app_ids.count("cli-product-lead") >= 1
    assert sent_app_ids[-1] == "cli-chief-of-staff"
    assert sent_app_ids.count("cli-chief-of-staff") >= 2

    run_trace = get_control_plane_service().get_required_run_trace(response.json()["runtrace_id"])
    assert run_trace.spoken_bot_ids == ["chief-of-staff", "product-lead"]
    assert run_trace.stop_reason == "no_resolved_next_hop"


def test_feishu_visible_handoff_stops_if_same_bot_is_requested_without_visible_name(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(employee_id="chief-of-staff", app_id="cli-chief-of-staff", app_secret="secret", display_name="OPC - Chief of Staff"),
            "product-lead": FeishuBotAppConfig(employee_id="product-lead", app_id="cli-product-lead", app_secret="secret", display_name="OPC - Product Lead"),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            turn_mode = kwargs.get("turn_mode", "source")
            handoff_context = kwargs.get("handoff_context")
            if employee_id == "chief-of-staff":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 先做组织，并请 Product Lead 接着补充产品判断。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    handoff_targets=["product-lead"],
                    turn_mode="source",
                )
            if turn_mode == "handoff_target" and handoff_context is not None and getattr(handoff_context, "retry_reason", None):
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-product-lead",
                    model_ref="openclaw:opc-product-lead",
                    reply_text="Product Lead 继续处理这件事。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-product-lead:feishu:group:test",
                    handoff_targets=["chief-of-staff"],
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id="opc-product-lead",
                model_ref="openclaw:opc-product-lead",
                reply_text="Product Lead 继续处理这件事。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-product-lead:feishu:group:test",
                handoff_targets=["chief-of-staff"],
                turn_mode="handoff_target",
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-repeat-stop-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-repeat-stop-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-repeat-stop-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-repeat-stop"}},
                "message": {
                    "message_id": f"om-group-repeat-stop-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_repeat_stop_{suffix}",
                    "content": '{"text":"@_user_1 先组织一下，再让 Product Lead 补充产品判断"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    assert [app_id for app_id, _ in sent_messages] == [
        "cli-chief-of-staff",
        "cli-product-lead",
    ]

    run_trace = get_control_plane_service().get_required_run_trace(response.json()["runtrace_id"])
    assert run_trace.handoff_contract_violation is True
    assert run_trace.stop_reason == "handoff_contract_violation"


def test_feishu_semantic_repeat_recall_allows_current_bot_to_return_for_closing(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_messages: list[tuple[str, str]] = []

    def fake_bot_config(employee_id: str):
        mapping = {
            "chief-of-staff": FeishuBotAppConfig(employee_id="chief-of-staff", app_id="cli-chief-of-staff", app_secret="secret", display_name="OPC - Chief of Staff"),
            "product-lead": FeishuBotAppConfig(employee_id="product-lead", app_id="cli-product-lead", app_secret="secret", display_name="OPC - Product Lead"),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            turn_mode = kwargs.get("turn_mode", "source")
            if employee_id == "chief-of-staff" and turn_mode == "source":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-chief-of-staff",
                    model_ref="openclaw:opc-chief-of-staff",
                    reply_text="Chief of Staff 先做组织，并请 Product Lead 给出产品判断。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-chief-of-staff:feishu:group:test",
                    handoff_targets=["product-lead"],
                    turn_mode="source",
                )
            if employee_id == "product-lead":
                return OpenClawChatResult(
                    employee_id=employee_id,
                    openclaw_agent_id="opc-product-lead",
                    model_ref="openclaw:opc-product-lead",
                    reply_text="Product Lead 给出产品判断。Chief of Staff 请你最后收口一下。",
                    strategy="openclaw_native_gateway",
                    session_key="agent:opc-product-lead:feishu:group:test",
                    handoff_targets=["chief-of-staff"],
                    turn_mode="handoff_target",
                )
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id="opc-chief-of-staff",
                model_ref="openclaw:opc-chief-of-staff",
                reply_text="Chief of Staff 最后收口：结论已经明确，可以进入下一步。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-chief-of-staff:feishu:group:test",
                turn_mode="handoff_target",
            )

        def infer_repeat_recall_targets(self, **kwargs):
            return OpenClawSemanticHandoffResult(
                needs_handoff=True,
                targets=[
                    OpenClawSemanticHandoffCandidate(
                        employee_id="chief-of-staff",
                        confidence=0.93,
                        reason="用户要求最后由 Chief of Staff 收口。",
                    )
                ],
            )

    def fake_send(self, request):
        sent_messages.append((request.app_id, request.text))
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-repeat-semantic-{len(sent_messages)}-{suffix}",
            status="sent",
            outbound_ref=f"fo-repeat-semantic-{len(sent_messages)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: fake_bot_config("chief-of-staff" if app_id == "cli-chief-of-staff" else "product-lead"),
    )
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-repeat-semantic-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-repeat-semantic"}},
                "message": {
                    "message_id": f"om-group-repeat-semantic-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_repeat_semantic_{suffix}",
                    "content": '{"text":"@_user_1 先组织一下，让 Product Lead 给判断，最后还是你来收口一下"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert response.status_code == 200
    sent_app_ids = [app_id for app_id, _ in sent_messages]
    assert sent_app_ids == [
        "cli-chief-of-staff",
        "cli-product-lead",
        "cli-chief-of-staff",
    ]
    run_trace = get_control_plane_service().get_required_run_trace(response.json()["runtrace_id"])
    assert run_trace.spoken_bot_ids == ["chief-of-staff", "product-lead"]
    assert run_trace.stop_reason == "no_resolved_next_hop"


def test_feishu_group_new_requests_reuse_existing_thread(monkeypatch) -> None:
    suffix = uuid4().hex[:8]

    def fake_bot_config(employee_id: str):
        return FeishuBotAppConfig(
            employee_id=employee_id,
            app_id="cli-design-lead",
            app_secret="secret",
            display_name="OPC - Design Lead",
        )

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            return OpenClawChatResult(
                employee_id="design-lead",
                openclaw_agent_id="opc-design-lead",
                model_ref="openclaw:opc-design-lead",
                reply_text="Design Lead 已收到。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-design-lead:feishu:group:test",
            )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_bot_config("design-lead"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-thread-{uuid4().hex[:8]}",
            status="sent",
            outbound_ref=f"fo-thread-{uuid4().hex[:8]}",
        ),
    )

    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-design-lead",
                "event_id": f"evt-group-thread-1-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-thread"}},
                "message": {
                    "message_id": f"om-group-thread-1-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_new_threads_{suffix}",
                    "content": '{"text":"@_user_1 回复我"}',
                    "mentions": [
                        {"id": {"open_id": "ou-design-per-app"}, "key": "@_user_1", "name": "Design Lead"},
                    ],
                },
            },
        },
    )
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-design-lead",
                "event_id": f"evt-group-thread-2-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-thread"}},
                "message": {
                    "message_id": f"om-group-thread-2-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": f"oc_group_new_threads_{suffix}",
                    "content": '{"text":"@_user_1 再回复我一次"}',
                    "mentions": [
                        {"id": {"open_id": "ou-design-per-app"}, "key": "@_user_1", "name": "Design Lead"},
                    ],
                },
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["thread_id"] == second.json()["thread_id"]


def test_feishu_send_endpoint_delegates_to_adapter(monkeypatch) -> None:
    fake_result = FeishuSendMessageResult(
        app_id="app-engineering-lead",
        receive_id_type="chat_id",
        receive_id="oc_group_room",
        message_id="om-sent-1",
        mention_employee_ids=["quality-lead"],
    )

    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: fake_result,
    )

    response = client.post(
        "/api/v1/feishu/send",
        json={
            "app_id": "app-engineering-lead",
            "chat_id": "oc_group_room",
            "text": "请 @质量 一起看下这个工单",
            "mention_employee_ids": ["quality-lead"],
        },
    )

    assert response.status_code == 200
    assert response.json()["message_id"] == "om-sent-1"


def test_feishu_send_text_message_retries_and_records_failure(monkeypatch) -> None:
    service = get_feishu_surface_adapter_service()
    settings = get_settings()
    base_count = len(service.list_outbound_messages())

    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: FeishuBotAppConfig(
            employee_id="chief-of-staff",
            app_id=app_id,
            app_secret="secret",
        ),
    )
    monkeypatch.setattr(service, "_get_tenant_access_token", lambda app_id, app_secret: "tenant-token")
    monkeypatch.setattr(service, "_post_json", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("timeout")))
    monkeypatch.setattr(settings, "feishu_send_max_attempts", 2)
    monkeypatch.setattr(settings, "feishu_send_retry_backoff_seconds", 0.0)

    result = service.send_text_message(
        FeishuSendMessageRequest(
            app_id="cli-retry-test",
            chat_id="oc_retry_room",
            text="发送失败测试",
            source_kind="manual",
        )
    )

    assert result.status == "failed"
    assert result.attempt_count == 2
    latest = service.list_outbound_messages()[-1]
    assert len(service.list_outbound_messages()) == base_count + 1
    assert latest.status == "failed"
    assert latest.attempt_count == 2
    assert latest.error_detail == "timeout"


def test_feishu_send_text_message_deduplicates_successful_outbound(monkeypatch) -> None:
    service = get_feishu_surface_adapter_service()
    settings = get_settings()
    post_calls = {"count": 0}

    class FakeBlob:
        object_id = "blob-1"
        bucket = "artifacts"
        object_key = "feishu/blob-1.txt"

    class FakeArtifactStore:
        def store_text(self, **kwargs):
            return FakeBlob()

    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: FeishuBotAppConfig(
            employee_id="product-lead",
            app_id=app_id,
            app_secret="secret",
        ),
    )
    monkeypatch.setattr(service, "_get_tenant_access_token", lambda app_id, app_secret: "tenant-token")
    monkeypatch.setattr(settings, "feishu_send_max_attempts", 1)
    monkeypatch.setattr(settings, "feishu_send_retry_backoff_seconds", 0.0)
    monkeypatch.setattr("app.feishu.services.get_artifact_store_service", lambda: FakeArtifactStore())

    def fake_post_json(*args, **kwargs):
        post_calls["count"] += 1
        return {"data": {"message_id": "om-dedupe-1"}}

    monkeypatch.setattr(service, "_post_json", fake_post_json)

    request = FeishuSendMessageRequest(
        app_id="cli-dedupe-test",
        chat_id="oc_dedupe_room",
        text="只发一次",
        source_kind="manual",
        idempotency_key=f"dedupe-key-{uuid4().hex[:8]}",
    )

    first = service.send_text_message(request)
    second = service.send_text_message(request)

    assert first.status == "sent"
    assert second.status == "deduplicated"
    assert post_calls["count"] == 1
    assert first.outbound_ref == second.outbound_ref


def test_feishu_send_text_message_drops_stale_runtrace_before_delivery(monkeypatch) -> None:
    service = get_feishu_surface_adapter_service()
    suffix = uuid4().hex[:8]
    post_calls = {"count": 0}

    def fake_bot_config(employee_id: str):
        return FeishuBotAppConfig(
            employee_id=employee_id,
            app_id="cli-chief-of-staff",
            app_secret="secret",
            display_name="OPC - Chief of Staff",
        )

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            employee_id = kwargs["employee_id"]
            return OpenClawChatResult(
                employee_id=employee_id,
                openclaw_agent_id=f"opc-{employee_id}",
                model_ref=f"openclaw:opc-{employee_id}",
                reply_text=f"{employee_id} 收到消息。",
                strategy="openclaw_native_gateway",
                session_key=f"agent:opc-{employee_id}:feishu:group:test",
            )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_bot_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_bot_config("chief-of-staff"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())

    chat_id = f"oc_group_stale_{suffix}"
    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-stale-first-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-stale"}},
                "message": {
                    "message_id": f"om-group-stale-first-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": chat_id,
                    "content": '{"text":"@_user_1 第一条"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-group-stale-second-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-group-stale"}},
                "message": {
                    "message_id": f"om-group-stale-second-{suffix}",
                    "message_type": "text",
                    "chat_type": "group",
                    "chat_id": chat_id,
                    "content": '{"text":"@_user_1 第二条，接管前一轮"}',
                    "mentions": [
                        {"id": {"open_id": "ou-chief-per-app"}, "key": "@_user_1", "name": "Chief of Staff"},
                    ],
                },
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()

    class FakeBlob:
        object_id = f"blob-stale-{suffix}"
        bucket = "artifacts"
        object_key = f"feishu/blob-stale-{suffix}.txt"

    class FakeArtifactStore:
        def store_text(self, **kwargs):
            return FakeBlob()

    monkeypatch.setattr(service, "_get_tenant_access_token", lambda app_id, app_secret: "tenant-token")
    monkeypatch.setattr("app.feishu.services.get_artifact_store_service", lambda: FakeArtifactStore())

    def fake_post_json(*args, **kwargs):
        post_calls["count"] += 1
        return {"data": {"message_id": f"om-stale-send-{suffix}"}}

    monkeypatch.setattr(service, "_post_json", fake_post_json)

    result = service.send_text_message(
        FeishuSendMessageRequest(
            app_id="cli-chief-of-staff",
            chat_id=chat_id,
            text="这是一条旧 run 的晚到回复",
            thread_ref=first_payload["thread_id"],
            runtrace_ref=first_payload["runtrace_id"],
            source_kind="auto_reply",
            delivery_guard_epoch=1,
        )
    )

    assert result.status == "dropped_stale"
    assert post_calls["count"] == 0

    latest = service.list_outbound_messages()[-1]
    assert latest.status == "dropped_stale"
    assert latest.dropped_as_stale is True
    assert latest.stale_drop_reason == "superseded_run"
    assert latest.runtrace_ref == first_payload["runtrace_id"]

    first_run = client.get(f"/api/v1/control-plane/run-traces/{first_payload['runtrace_id']}").json()
    second_run = client.get(f"/api/v1/control-plane/run-traces/{second_payload['runtrace_id']}").json()
    assert any(event["event_type"] == "stale_reply_dropped" for event in first_run["events"])
    assert second_run["delivery_guard_epoch"] == 2


def test_feishu_send_text_message_records_delivery_guard_passed(monkeypatch) -> None:
    service = get_feishu_surface_adapter_service()
    suffix = uuid4().hex[:8]

    intake_response = client.post(
        "/api/v1/conversations/intake",
        json={
            "surface": "feishu_dm",
            "channel_id": f"feishu:dm:delivery-guard-{suffix}",
            "participant_ids": ["vincent", "feishu-chief-of-staff"],
            "bound_agent_ids": ["chief-of-staff"],
            "command": {"intent": "测试 delivery guard passed"},
        },
    )
    assert intake_response.status_code == 200
    intake_payload = intake_response.json()
    thread_id = intake_payload["thread"]["thread_id"]
    runtrace_id = intake_payload["command_result"]["run_trace"]["runtrace_id"]
    get_conversation_service().set_active_runtrace(
        thread_id,
        runtrace_id=runtrace_id,
        delivery_guard_epoch=3,
    )

    class FakeBlob:
        object_id = f"blob-guard-{suffix}"
        bucket = "artifacts"
        object_key = f"feishu/blob-guard-{suffix}.txt"

    class FakeArtifactStore:
        def store_text(self, **kwargs):
            return FakeBlob()

    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: FeishuBotAppConfig(
            employee_id="chief-of-staff",
            app_id=app_id,
            app_secret="secret",
            display_name="OPC - Chief of Staff",
        ),
    )
    monkeypatch.setattr(service, "_get_tenant_access_token", lambda app_id, app_secret: "tenant-token")
    monkeypatch.setattr("app.feishu.services.get_artifact_store_service", lambda: FakeArtifactStore())
    monkeypatch.setattr(
        service,
        "_post_json",
        lambda *args, **kwargs: {"data": {"message_id": f"om-delivery-guard-{suffix}"}},
    )

    result = service.send_text_message(
        FeishuSendMessageRequest(
            app_id="cli-chief-of-staff",
            chat_id=f"oc_delivery_guard_{suffix}",
            text="这是一条通过 delivery guard 的回复",
            thread_ref=thread_id,
            runtrace_ref=runtrace_id,
            source_kind="auto_reply",
            delivery_guard_epoch=3,
        )
    )

    assert result.status == "sent"

    run_trace = client.get(f"/api/v1/control-plane/run-traces/{runtrace_id}").json()
    guard_events = [event for event in run_trace["events"] if event["event_type"] == "delivery_guard_passed"]
    assert len(guard_events) == 1
    assert guard_events[0]["metadata"]["thread_id"] == thread_id
    assert guard_events[0]["metadata"]["runtrace_id"] == runtrace_id
    assert guard_events[0]["metadata"]["delivery_guard_epoch"] == "3"
    assert guard_events[0]["metadata"]["source_kind"] == "auto_reply"


def test_feishu_real_bot_event_uses_openclaw_dialogue_reply(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    captured: dict[str, str] = {}

    def fake_config(employee_id: str):
        mapping = {
            "product-lead": FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product-live",
                app_secret="secret",
                bot_open_id="ou-product-live",
                display_name="OPC - Product Lead",
            ),
        }
        return mapping.get(employee_id)

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            return OpenClawChatResult(
                employee_id="product-lead",
                model_ref="bailian/kimi-k2.5",
                reply_text="这是 Product Lead 的 OpenClaw 风格回复。",
                strategy="openclaw_live",
            )

    def fake_send(self, request):
        captured["text"] = request.text
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-live-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_config("product-lead"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-product-live",
                "event_id": f"evt-live-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-live"}},
                "message": {
                    "message_id": f"om-live-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_live_{suffix}",
                    "content": "{\"text\":\"给我一个产品判断\"}",
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "processed"
    assert captured["text"] == "这是 Product Lead 的 OpenClaw 风格回复。"


def test_feishu_dm_can_emit_visible_follow_up_reply(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_texts: list[str] = []

    def fake_config(employee_id: str):
        return FeishuBotAppConfig(
            employee_id=employee_id,
            app_id="cli-follow-up",
            app_secret="secret",
            bot_open_id="ou-follow-up",
            display_name="OPC - Chief of Staff",
        )

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            return OpenClawChatResult(
                employee_id="chief-of-staff",
                openclaw_agent_id="opc-chief-of-staff",
                model_ref="bailian/kimi-k2.5",
                reply_text="这是第一条回复。",
                follow_up_texts=["这是第二条可见 follow-up。", "这是第三条可见 follow-up。"],
                strategy="openclaw_gateway_live",
                session_key="agent:opc-chief-of-staff:feishu:dm:test",
            )

    def fake_send(self, request):
        sent_texts.append(request.text)
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=f"om-sent-follow-up-{len(sent_texts)}-{suffix}",
        )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_config("chief-of-staff"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr("app.feishu.services.FeishuSurfaceAdapterService.send_text_message", fake_send)

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-follow-up",
                "event_id": f"evt-follow-up-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-follow-up"}},
                "message": {
                    "message_id": f"om-follow-up-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_follow_up_{suffix}",
                    "content": "{\"text\":\"继续展开一下\"}",
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["reply_count"] == 3
    assert sent_texts == ["这是第一条回复。", "这是第二条可见 follow-up。", "这是第三条可见 follow-up。"]


def test_feishu_dead_letter_endpoint_and_replay(monkeypatch) -> None:
    service = get_feishu_surface_adapter_service()
    settings = get_settings()

    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: FeishuBotAppConfig(
            employee_id="chief-of-staff",
            app_id=app_id,
            app_secret="secret",
        ),
    )
    monkeypatch.setattr(service, "_get_tenant_access_token", lambda app_id, app_secret: "tenant-token")
    monkeypatch.setattr(settings, "feishu_send_max_attempts", 1)
    monkeypatch.setattr(settings, "feishu_send_retry_backoff_seconds", 0.0)
    monkeypatch.setattr(service, "_post_json", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("network down")))

    failed = service.send_text_message(
        FeishuSendMessageRequest(
            app_id="cli-dead-letter-test",
            chat_id="oc_dead_letter_room",
            text="dead letter 需要重放",
            source_kind="manual",
        )
    )
    assert failed.status == "failed"

    dead_letters_response = client.get("/api/v1/feishu/dead-letters")
    assert dead_letters_response.status_code == 200
    target = next(item for item in dead_letters_response.json() if item["outbound_id"] == failed.outbound_ref)
    dead_letter_detail_response = client.get(f"/api/v1/feishu/dead-letters/{target['outbound_id']}")
    assert dead_letter_detail_response.status_code == 200
    assert dead_letter_detail_response.json()["dead_letter"]["outbound_id"] == target["outbound_id"]

    class FakeBlob:
        object_id = "blob-replay"
        bucket = "artifacts"
        object_key = "feishu/blob-replay.txt"

    class FakeArtifactStore:
        def store_text(self, **kwargs):
            return FakeBlob()

    monkeypatch.setattr("app.feishu.services.get_artifact_store_service", lambda: FakeArtifactStore())
    monkeypatch.setattr(service, "_post_json", lambda *args, **kwargs: {"data": {"message_id": "om-replay-ok"}})

    replay_response = client.post(f"/api/v1/feishu/outbound-messages/{target['outbound_id']}/replay")

    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["source_outbound_ref"] == target["outbound_id"]
    assert replay_payload["replay_result"]["status"] in {"sent", "deduplicated"}

    replay_audit_response = client.get(f"/api/v1/feishu/replay-audit?source_outbound_ref={target['outbound_id']}")
    assert replay_audit_response.status_code == 200
    assert replay_audit_response.json()
    assert replay_audit_response.json()[0]["replay_source_outbound_ref"] == target["outbound_id"]

    latest_dead_letters = client.get("/api/v1/feishu/dead-letters").json()
    assert all(item["outbound_id"] != target["outbound_id"] for item in latest_dead_letters)


def test_feishu_new_command_starts_fresh_thread(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_texts: list[str] = []

    def fake_config(employee_id: str):
        return FeishuBotAppConfig(
            employee_id=employee_id,
            app_id="cli-chief-of-staff",
            app_secret="secret",
            display_name="OPC - Chief of Staff",
        )

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            return OpenClawChatResult(
                employee_id="chief-of-staff",
                openclaw_agent_id="opc-chief-of-staff",
                model_ref="openclaw:opc-chief-of-staff",
                reply_text="这是新会话里的第一条业务回复。",
                strategy="openclaw_native_gateway",
                session_key="agent:opc-chief-of-staff:feishu:dm:test-new",
            )

    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_config("chief-of-staff"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: (
            sent_texts.append(request.text),
            FeishuSendMessageResult(
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=f"om-new-{suffix}",
            ),
        )[1],
    )

    first = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-new-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-new"}},
                "message": {
                    "message_id": f"om-new-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_new_{suffix}",
                    "content": "{\"text\":\"/new\"}",
                },
            },
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["status"] == "processed"
    assert first_payload["dispatch_mode"] == "new_conversation_marker"
    assert sent_texts and "已开启一个新对话" in sent_texts[-1]

    thread_id = first_payload["thread_id"]
    second = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-chief-of-staff",
                "event_id": f"evt-new-follow-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-new"}},
                "message": {
                    "message_id": f"om-new-follow-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_new_{suffix}",
                    "content": "{\"text\":\"继续这个新会话\"}",
                },
            },
        },
    )
    assert second.status_code == 200
    assert second.json()["thread_id"] == thread_id


def test_feishu_streaming_chunks_long_reply(monkeypatch) -> None:
    suffix = uuid4().hex[:8]
    sent_texts: list[str] = []
    settings = get_settings()

    def fake_config(employee_id: str):
        return FeishuBotAppConfig(
            employee_id=employee_id,
            app_id="cli-stream-test",
            app_secret="secret",
            display_name="OPC - Chief of Staff",
        )

    class FakeDialogueService:
        def generate_reply(self, **kwargs):
            return OpenClawChatResult(
                employee_id="chief-of-staff",
                openclaw_agent_id="opc-chief-of-staff",
                model_ref="openclaw:opc-chief-of-staff",
                reply_text="第一段内容。" + "\n\n" + "第二段内容。" * 40,
                follow_up_texts=[],
                strategy="openclaw_native_gateway",
                session_key="agent:opc-chief-of-staff:feishu:dm:test",
            )

    monkeypatch.setattr(settings, "feishu_stream_chunk_chars", 120)
    monkeypatch.setattr(settings, "feishu_stream_chunk_delay_seconds", 0.0)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_employee_id", fake_config)
    monkeypatch.setattr("app.feishu.services.get_feishu_bot_app_config_by_app_id", lambda app_id: fake_config("chief-of-staff"))
    monkeypatch.setattr("app.feishu.services.get_openclaw_dialogue_service", lambda: FakeDialogueService())
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService.send_text_message",
        lambda self, request: (
            sent_texts.append(request.text),
            FeishuSendMessageResult(
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=f"om-stream-{len(sent_texts)}-{suffix}",
            ),
        )[1],
    )

    response = client.post(
        "/api/v1/feishu/events",
        json={
            "schema": "2.0",
            "header": {
                "event_type": "im.message.receive_v1",
                "app_id": "cli-stream-test",
                "event_id": f"evt-stream-{suffix}",
            },
            "event": {
                "sender": {"sender_id": {"open_id": "ou-user-stream"}},
                "message": {
                    "message_id": f"om-stream-{suffix}",
                    "message_type": "text",
                    "chat_type": "p2p",
                    "chat_id": f"oc_dm_stream_{suffix}",
                    "content": "{\"text\":\"分段回复我\"}",
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["reply_count"] >= 2
    assert len(sent_texts) >= 2
