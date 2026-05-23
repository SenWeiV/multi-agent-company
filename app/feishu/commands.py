from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

_KNOWN_COMMANDS = {"new", "end", "status", "reset"}


@dataclass
class ParsedCommand:
    command: str
    argument: str = ""


def parse_feishu_command(text: str) -> ParsedCommand | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    lowered = stripped.lower()
    for cmd in _KNOWN_COMMANDS:
        if lowered == f"/{cmd}":
            return ParsedCommand(command=cmd)
        if cmd == "new" and lowered.startswith("/new "):
            argument = stripped[5:].strip()
            return ParsedCommand(command="new", argument=argument)
    return None


def generate_topic_id() -> str:
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    random_part = uuid4().hex[:6]
    return f"t_{date_part}_{random_part}"
