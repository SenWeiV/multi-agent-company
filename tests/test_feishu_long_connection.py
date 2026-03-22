from __future__ import annotations

from app.feishu.long_connection import build_long_connection_bindings
from app.feishu.models import FeishuBotAppConfig
from app.feishu.services import feishu_sdk_event_to_payload


def test_build_long_connection_bindings_uses_bot_configs(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.feishu.long_connection.get_feishu_bot_app_configs",
        lambda: [
            FeishuBotAppConfig(
                employee_id="chief-of-staff",
                app_id="cli-chief",
                app_secret="secret-chief",
                display_name="OPC - Chief of Staff",
            ),
            FeishuBotAppConfig(
                employee_id="product-lead",
                app_id="cli-product",
                app_secret="secret-product",
            ),
        ],
    )

    bindings = build_long_connection_bindings()

    assert [binding.employee_id for binding in bindings] == ["chief-of-staff", "product-lead"]
    assert bindings[0].display_name == "OPC - Chief of Staff"
    assert bindings[1].display_name == "product-lead"


def test_feishu_sdk_event_to_payload_recursively_serializes_objects() -> None:
    class SenderId:
        def __init__(self) -> None:
            self.open_id = "ou-user-1"

    class Sender:
        def __init__(self) -> None:
            self.sender_id = SenderId()

    class Message:
        def __init__(self) -> None:
            self.message_id = "om-123"
            self.content = "{\"text\":\"hello\"}"

    class Event:
        def __init__(self) -> None:
            self.header = {"event_type": "im.message.receive_v1"}
            self.event = {"sender": Sender(), "message": Message()}

    payload = feishu_sdk_event_to_payload(Event())

    assert payload["header"]["event_type"] == "im.message.receive_v1"
    assert payload["event"]["sender"]["sender_id"]["open_id"] == "ou-user-1"
    assert payload["event"]["message"]["message_id"] == "om-123"
