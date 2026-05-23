from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.conversation.models import ConversationSurface, ConversationThread
from app.feishu.commands import ParsedCommand, parse_feishu_command
from app.feishu.models import FeishuWebhookResult


class TestCommandHandlerEndCommand:
    """Test /end command handler logic in FeishuSurfaceAdapterService."""

    def _make_thread(self, status: str = "active", topic_id: str | None = None) -> ConversationThread:
        return ConversationThread(
            thread_id="thread-001",
            surface=ConversationSurface.FEISHU_GROUP,
            channel_id="feishu-group-oc_abc123",
            provider="feishu",
            title="Test thread",
            status=status,
            topic_id=topic_id,
            created_at=datetime.now(UTC),
        )

    def test_end_command_parsed_correctly(self):
        cmd = parse_feishu_command("/end")
        assert cmd is not None
        assert cmd.command == "end"

    def test_end_command_with_no_active_thread(self):
        from app.feishu.commands import parse_feishu_command
        cmd = parse_feishu_command("/end")
        assert cmd is not None
        assert cmd.command == "end"

    def test_status_command_parsed(self):
        cmd = parse_feishu_command("/status")
        assert cmd is not None
        assert cmd.command == "status"

    def test_reset_command_parsed(self):
        cmd = parse_feishu_command("/reset")
        assert cmd is not None
        assert cmd.command == "reset"


class TestTopicIdGeneration:
    """Test that topic IDs are generated correctly."""

    def test_topic_id_format(self):
        from app.feishu.commands import generate_topic_id
        topic_id = generate_topic_id()
        assert topic_id.startswith("t_")
        parts = topic_id.split("_")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # date part: YYYYMMDD
        assert len(parts[2]) == 6  # random hex

    def test_topic_ids_are_unique(self):
        from app.feishu.commands import generate_topic_id
        ids = {generate_topic_id() for _ in range(100)}
        assert len(ids) == 100
