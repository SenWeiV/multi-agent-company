from __future__ import annotations

from unittest.mock import MagicMock

from app.openclaw.models import OpenClawAgentBinding, OpenClawSessionBinding
from app.openclaw.services import OpenClawProvisioningService


def _make_provisioning_service() -> OpenClawProvisioningService:
    service = OpenClawProvisioningService.__new__(OpenClawProvisioningService)
    service._bindings = MagicMock()
    binding = OpenClawAgentBinding(
        employee_id="chief-of-staff",
        openclaw_agent_id="opc-chief-of-staff",
        workspace_home_ref="/home/node/.openclaw",
        workspace_path="/home/node/.openclaw/agents/opc-chief-of-staff",
        agent_dir="opc-chief-of-staff",
        primary_model_ref="deepseek-v4-pro",
        tool_profile="standard",
        sandbox_profile="docker",
        department="executive",
    )
    service.get_agent_binding = MagicMock(return_value=binding)
    return service


class TestSessionBindingWithTopic:
    def test_get_session_binding_without_topic(self):
        service = _make_provisioning_service()
        result = service.get_session_binding("chief-of-staff", "feishu_group", "oc_abc123")
        assert result.session_key == "agent:opc-chief-of-staff:feishu:group:oc_abc123"

    def test_get_session_binding_with_topic(self):
        service = _make_provisioning_service()
        result = service.get_session_binding("chief-of-staff", "feishu_group", "oc_abc123", topic_id="t_20260522_001")
        assert result.session_key == "agent:opc-chief-of-staff:feishu:group:oc_abc123:topic:t_20260522_001"

    def test_get_session_binding_dm_ignores_topic(self):
        service = _make_provisioning_service()
        result = service.get_session_binding("chief-of-staff", "feishu_dm", "oc_abc123", topic_id="t_20260522_001")
        assert result.session_key == "agent:opc-chief-of-staff:feishu:dm:oc_abc123"
        assert "topic" not in result.session_key

    def test_different_topics_get_different_keys(self):
        service = _make_provisioning_service()
        r1 = service.get_session_binding("chief-of-staff", "feishu_group", "oc_abc123", topic_id="t_001")
        r2 = service.get_session_binding("chief-of-staff", "feishu_group", "oc_abc123", topic_id="t_002")
        assert r1.session_key != r2.session_key

    def test_session_binding_fields(self):
        service = _make_provisioning_service()
        result = service.get_session_binding("chief-of-staff", "feishu_group", "oc_abc123", topic_id="t_001")
        assert result.employee_id == "chief-of-staff"
        assert result.openclaw_agent_id == "opc-chief-of-staff"
        assert result.surface == "feishu_group"
        assert result.channel_id == "oc_abc123"


class TestRotateSession:
    def test_rotate_session_creates_new_key(self):
        service = _make_provisioning_service()
        result = service.rotate_session("chief-of-staff", "feishu_group", "oc_abc123", "t_new_topic")
        assert "topic:t_new_topic" in result.session_key

    def test_rotate_session_old_key_unchanged(self):
        service = _make_provisioning_service()
        old = service.get_session_binding("chief-of-staff", "feishu_group", "oc_abc123")
        new = service.rotate_session("chief-of-staff", "feishu_group", "oc_abc123", "t_new_topic")
        assert old.session_key == "agent:opc-chief-of-staff:feishu:group:oc_abc123"
        assert new.session_key == "agent:opc-chief-of-staff:feishu:group:oc_abc123:topic:t_new_topic"
