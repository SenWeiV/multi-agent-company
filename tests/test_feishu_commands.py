from __future__ import annotations

from app.feishu.commands import ParsedCommand, parse_feishu_command


class TestParseFeishuCommand:
    def test_new_only(self):
        result = parse_feishu_command("/new")
        assert result == ParsedCommand(command="new", argument="")

    def test_new_with_message(self):
        result = parse_feishu_command("/new 做一个美股看板产品")
        assert result == ParsedCommand(command="new", argument="做一个美股看板产品")

    def test_new_with_whitespace(self):
        result = parse_feishu_command("  /new   评估AI市场  ")
        assert result == ParsedCommand(command="new", argument="评估AI市场")

    def test_end(self):
        result = parse_feishu_command("/end")
        assert result == ParsedCommand(command="end", argument="")

    def test_status(self):
        result = parse_feishu_command("/status")
        assert result == ParsedCommand(command="status", argument="")

    def test_reset(self):
        result = parse_feishu_command("/reset")
        assert result == ParsedCommand(command="reset", argument="")

    def test_non_command_returns_none(self):
        assert parse_feishu_command("hello world") is None
        assert parse_feishu_command("not a /command") is None
        assert parse_feishu_command("@Chief of Staff 帮我分析") is None

    def test_case_insensitive(self):
        assert parse_feishu_command("/NEW") == ParsedCommand(command="new", argument="")
        assert parse_feishu_command("/End") == ParsedCommand(command="end", argument="")
        assert parse_feishu_command("/STATUS") == ParsedCommand(command="status", argument="")
        assert parse_feishu_command("/Reset") == ParsedCommand(command="reset", argument="")

    def test_new_case_preserves_argument(self):
        result = parse_feishu_command("/NEW Do Something Important")
        assert result == ParsedCommand(command="new", argument="Do Something Important")

    def test_slash_only_returns_none(self):
        assert parse_feishu_command("/") is None

    def test_unknown_command_returns_none(self):
        assert parse_feishu_command("/unknown") is None
        assert parse_feishu_command("/help") is None
