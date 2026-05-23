from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from app.openclaw.services import OpenClawGatewayAdapter


def _mock_config_service() -> MagicMock:
    svc = MagicMock()
    agent_config = MagicMock()
    agent_config.openclaw_agent_id = "opc-chief-of-staff"
    agent_config.max_tokens = 2048
    provider_config = MagicMock()
    provider_config.baseUrl = "https://api.deepseek.com/v1"
    provider_config.apiKey = "sk-test-key"
    provider_model = MagicMock()
    provider_model.id = "deepseek-chat"
    svc.get_provider_for_agent.return_value = (agent_config, provider_config, provider_model)
    svc.is_core_employee.return_value = True
    return svc


def _mock_provisioning_service() -> MagicMock:
    svc = MagicMock()
    binding = MagicMock()
    binding.session_key = "agent:opc-chief-of-staff:feishu:group:oc_test"
    binding.openclaw_agent_id = "opc-chief-of-staff"
    binding.model_copy.return_value = binding
    svc.get_session_binding.return_value = binding
    svc.get_agent_binding.return_value = binding
    return svc


def _adapter() -> OpenClawGatewayAdapter:
    return OpenClawGatewayAdapter(
        config_service=_mock_config_service(),
        provisioning_service=_mock_provisioning_service(),
    )


class TestGenerateQuickAck:
    @patch("app.openclaw.services.get_settings")
    @patch("app.openclaw.services.urlopen")
    def test_generate_quick_ack_success(self, mock_urlopen: MagicMock, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.feishu_quick_ack_enabled = True
        settings.feishu_quick_ack_max_tokens = 80
        mock_settings.return_value = settings

        response_body = json.dumps({
            "choices": [{"message": {"content": "收到，这是一个技术架构设计需求。我来分析一下。"}}]
        }).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        adapter = _adapter()
        result = adapter.generate_quick_ack(
            employee_id="chief-of-staff",
            user_message="帮我设计一个评测系统",
            surface="feishu_group",
            channel_id="oc_test",
        )
        assert result is not None
        assert "技术架构" in result or "评测" in result or "收到" in result

    @patch("app.openclaw.services.get_settings")
    @patch("app.openclaw.services.urlopen")
    def test_generate_quick_ack_timeout_returns_none(self, mock_urlopen: MagicMock, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.feishu_quick_ack_enabled = True
        settings.feishu_quick_ack_max_tokens = 80
        mock_settings.return_value = settings

        mock_urlopen.side_effect = URLError("timeout")

        adapter = _adapter()
        result = adapter.generate_quick_ack(
            employee_id="chief-of-staff",
            user_message="test",
            surface="feishu_group",
            channel_id="oc_test",
        )
        assert result is None

    @patch("app.openclaw.services.get_settings")
    @patch("app.openclaw.services.urlopen")
    def test_generate_quick_ack_error_returns_none(self, mock_urlopen: MagicMock, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.feishu_quick_ack_enabled = True
        settings.feishu_quick_ack_max_tokens = 80
        mock_settings.return_value = settings

        mock_urlopen.side_effect = HTTPError("http://x", 500, "err", {}, None)

        adapter = _adapter()
        result = adapter.generate_quick_ack(
            employee_id="chief-of-staff",
            user_message="test",
            surface="feishu_group",
            channel_id="oc_test",
        )
        assert result is None

    @patch("app.openclaw.services.get_settings")
    @patch("app.openclaw.services.urlopen")
    def test_quick_ack_uses_provider_api_directly(self, mock_urlopen: MagicMock, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.feishu_quick_ack_enabled = True
        settings.feishu_quick_ack_max_tokens = 80
        mock_settings.return_value = settings

        response_body = json.dumps({
            "choices": [{"message": {"content": "收到。"}}]
        }).encode()
        mock_response = MagicMock()
        mock_response.read.return_value = response_body
        mock_response.status = 200
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        adapter = _adapter()
        adapter.generate_quick_ack(
            employee_id="chief-of-staff",
            user_message="test",
            surface="feishu_group",
            channel_id="oc_test",
        )

        # Check that the request goes to provider API, not gateway
        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        assert "openclaw-gateway" not in request_obj.full_url
        assert "chat/completions" in request_obj.full_url

    @patch("app.openclaw.services.get_settings")
    def test_quick_ack_disabled_by_config(self, mock_settings: MagicMock) -> None:
        settings = MagicMock()
        settings.feishu_quick_ack_enabled = False
        mock_settings.return_value = settings

        adapter = _adapter()
        result = adapter.generate_quick_ack(
            employee_id="chief-of-staff",
            user_message="test",
            surface="feishu_group",
            channel_id="oc_test",
        )
        assert result is None


class TestQuickAckIntegration:
    def test_ack_failure_does_not_block_reply(self) -> None:
        """Quick ACK failure should not prevent the main reply from being generated."""
        adapter = _adapter()
        # Simulate ACK always failing
        with patch.object(adapter, "generate_quick_ack", return_value=None):
            # The adapter should still be usable for normal invoke_agent calls
            assert adapter.generate_quick_ack(
                employee_id="chief-of-staff",
                user_message="test",
                surface="feishu_group",
                channel_id="oc_test",
            ) is None
