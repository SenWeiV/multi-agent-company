from __future__ import annotations

import re

from app.orchestration.models import (
    DiscussionPhase,
    DiscussionPlan,
    DiscussionRole,
    PhaseParticipant,
    PhaseTransitionSignal,
)

_PHASE_LINE_RE = re.compile(
    r"-\s*phase:\s*(?P<phase_id>[^\|]+?)\s*"
    r"\|\s*lead:\s*(?P<lead>[^\|]+?)\s*"
    r"(?:\|\s*with:\s*(?P<with>[^\|]+?))?\s*"
    r"(?:\|\s*max_turns:\s*(?P<max_turns>\d+))?\s*$"
)


def parse_phase_plan(
    raw_reply: str,
    *,
    valid_employee_ids: set[str] | None = None,
    default_max_turns: int = 10,
) -> DiscussionPlan | None:
    lines = raw_reply.splitlines()

    start_idx: int | None = None
    end_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.upper() == "PHASE_PLAN:":
            start_idx = i
        elif stripped.upper() == "END_PHASE_PLAN" and start_idx is not None:
            end_idx = i
            break

    if start_idx is None or end_idx is None:
        return None

    phases: list[DiscussionPhase] = []
    for line in lines[start_idx + 1 : end_idx]:
        stripped = line.strip()
        if not stripped:
            continue
        match = _PHASE_LINE_RE.match(stripped)
        if match is None:
            continue

        phase_id = match.group("phase_id").strip()
        lead_id = match.group("lead").strip()
        with_raw = match.group("with")
        max_turns_raw = match.group("max_turns")

        if valid_employee_ids and lead_id not in valid_employee_ids:
            continue

        participants: list[PhaseParticipant] = []
        if with_raw:
            for eid in (s.strip() for s in with_raw.split(",")):
                if not eid:
                    continue
                if valid_employee_ids and eid not in valid_employee_ids:
                    continue
                participants.append(
                    PhaseParticipant(employee_id=eid, role=DiscussionRole.PARTICIPANT)
                )

        max_turns = int(max_turns_raw) if max_turns_raw else default_max_turns

        phases.append(
            DiscussionPhase(
                phase_id=phase_id,
                title=phase_id.replace("-", " ").title(),
                lead_id=lead_id,
                participants=participants,
                max_turns=max_turns,
            )
        )

    if not phases:
        return None

    return DiscussionPlan(phases=phases)


def parse_phase_signals(raw_reply: str) -> PhaseTransitionSignal:
    phase_complete = False
    next_speaker: str | None = None
    reason: str | None = None

    for line in raw_reply.splitlines():
        stripped = line.strip()
        upper = stripped.upper()

        if upper.startswith("PHASE_COMPLETE:"):
            payload = stripped.split(":", 1)[1].strip().lower()
            phase_complete = payload in {"yes", "true", "1"}

        elif upper.startswith("DISCUSS_WITH:"):
            payload = stripped.split(":", 1)[1].strip()
            if "|" in payload:
                target_part, _, reason_part = payload.partition("|")
                next_speaker = target_part.strip() or None
                reason = reason_part.strip() or None
            else:
                next_speaker = payload.strip() or None

    return PhaseTransitionSignal(
        phase_complete=phase_complete,
        next_speaker=next_speaker,
        reason=reason,
    )


_PHASE_PLAN_BLOCK_RE = re.compile(
    r"^PHASE_PLAN:\s*\n(?:.*\n)*?END_PHASE_PLAN\s*$",
    re.MULTILINE,
)


def strip_phase_protocol_lines(raw_reply: str) -> str:
    result = _PHASE_PLAN_BLOCK_RE.sub("", raw_reply)

    cleaned_lines: list[str] = []
    for line in result.splitlines():
        upper = line.strip().upper()
        if upper.startswith("PHASE_COMPLETE:") or upper.startswith("DISCUSS_WITH:"):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
