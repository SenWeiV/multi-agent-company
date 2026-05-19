"""Tests for RunTrace event emission and edge case hardening in PhaseOrchestrator."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.orchestration.models import (
    DiscussionPhase,
    DiscussionPlan,
    DiscussionRole,
    PhaseParticipant,
    PhaseStatus,
)
from app.orchestration.phase_orchestrator import PhaseOrchestrator


def _make_plan(phases: list[DiscussionPhase]) -> DiscussionPlan:
    return DiscussionPlan(phases=phases)


def _phase(
    phase_id: str,
    lead_id: str,
    participant_ids: list[str] | None = None,
    max_turns: int = 10,
) -> DiscussionPhase:
    participants = [
        PhaseParticipant(employee_id=eid, role=DiscussionRole.PARTICIPANT)
        for eid in (participant_ids or [])
    ]
    return DiscussionPhase(
        phase_id=phase_id,
        title=phase_id.replace("-", " ").title(),
        lead_id=lead_id,
        participants=participants,
        max_turns=max_turns,
    )


def _make_generate_reply(replies: dict[str, list[str]]) -> Any:
    call_counts: dict[str, int] = {}

    def _generate(*, employee_id: str, **kwargs: Any) -> MagicMock:
        idx = call_counts.get(employee_id, 0)
        call_counts[employee_id] = idx + 1
        reply_list = replies.get(employee_id, ["Default reply."])
        text = reply_list[idx] if idx < len(reply_list) else reply_list[-1]

        result = MagicMock()
        result.reply_text = text
        result.follow_up_texts = []
        result.handoff_targets = []
        result.handoff_reason = None
        result.strategy = "native"
        result.model_ref = "test"
        result.session_key = f"session:{employee_id}"
        result.error_detail = None
        return result

    mock = MagicMock(side_effect=_generate)
    return mock


def _make_send_message() -> MagicMock:
    result = MagicMock()
    result.status = "sent"
    result.error_detail = None
    send = MagicMock(return_value=result)
    return send


def _build_orchestrator(
    plan: DiscussionPlan,
    generate_reply: Any,
    send_message: Any | None = None,
    global_turn_limit: int = 40,
    source_reply_text: str = "Chief of Staff framing.",
    valid_employee_ids: set[str] | None = None,
    emit_trace_event: Any | None = None,
) -> PhaseOrchestrator:
    return PhaseOrchestrator(
        plan=plan,
        global_turn_limit=global_turn_limit,
        initial_visible_turn_count=1,
        generate_reply_fn=generate_reply,
        send_message_fn=send_message or _make_send_message(),
        source_reply_text=source_reply_text,
        valid_employee_ids=valid_employee_ids
        or {
            "opc-product-lead",
            "opc-research-lead",
            "opc-engineering-lead",
            "opc-quality-lead",
            "opc-delivery-lead",
        },
        emit_trace_event=emit_trace_event,
    )


# --- Trace event tests ---


def test_phase_started_event_emitted() -> None:
    """PhaseOrchestrator emits a phase_started event when entering a phase."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply(
        {"opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"]}
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    started = [e for e in trace_events if e["type"] == "phase_started"]
    assert len(started) == 1
    assert "p1" in started[0]["message"]
    assert started[0]["metadata"]["phase_id"] == "p1"
    assert started[0]["metadata"]["lead_id"] == "opc-product-lead"


def test_phase_completed_event_emitted() -> None:
    """PhaseOrchestrator emits a phase_completed event when a phase completes."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply(
        {"opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"]}
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    completed = [e for e in trace_events if e["type"] == "phase_completed"]
    assert len(completed) == 1
    assert "p1" in completed[0]["message"]
    assert completed[0]["metadata"]["phase_id"] == "p1"


def test_phase_speaker_turn_events_emitted() -> None:
    """Each speaker turn within a phase emits a phase_speaker_turn event."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Initial.", "Final.\nPHASE_COMPLETE: yes"],
            "opc-research-lead": ["Input."],
        }
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    turns = [e for e in trace_events if e["type"] == "phase_speaker_turn"]
    assert len(turns) == 3
    assert turns[0]["metadata"]["speaker_id"] == "opc-product-lead"
    assert turns[0]["metadata"]["role"] == "lead"
    assert turns[1]["metadata"]["speaker_id"] == "opc-research-lead"
    assert turns[1]["metadata"]["role"] == "participant"
    assert turns[2]["metadata"]["speaker_id"] == "opc-product-lead"


def test_phase_forced_completion_event() -> None:
    """When max_turns is reached without PHASE_COMPLETE, emit phase_forced_completion."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"], max_turns=2)]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Keep going."] * 5,
            "opc-research-lead": ["More."] * 5,
        }
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    forced = [e for e in trace_events if e["type"] == "phase_forced_completion"]
    assert len(forced) == 1
    assert forced[0]["metadata"]["phase_id"] == "p1"
    assert forced[0]["metadata"]["turns_used"] == "2"


def test_multi_phase_trace_events() -> None:
    """Multiple phases produce started/completed events for each phase."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan(
        [
            _phase("p1", "opc-product-lead"),
            _phase("p2", "opc-engineering-lead"),
        ]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
            "opc-engineering-lead": ["Built.\nPHASE_COMPLETE: yes"],
        }
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    started = [e for e in trace_events if e["type"] == "phase_started"]
    completed = [e for e in trace_events if e["type"] == "phase_completed"]
    assert len(started) == 2
    assert len(completed) == 2
    assert started[0]["metadata"]["phase_id"] == "p1"
    assert started[1]["metadata"]["phase_id"] == "p2"


def test_skipped_phase_emits_phase_skipped_event() -> None:
    """A phase with invalid lead emits phase_skipped, not phase_started."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan(
        [
            _phase("p1", "invalid-lead"),
            _phase("p2", "opc-engineering-lead"),
        ]
    )
    gen = _make_generate_reply(
        {"opc-engineering-lead": ["Built.\nPHASE_COMPLETE: yes"]}
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    skipped = [e for e in trace_events if e["type"] == "phase_skipped"]
    assert len(skipped) == 1
    assert skipped[0]["metadata"]["phase_id"] == "p1"
    assert skipped[0]["metadata"]["lead_id"] == "invalid-lead"


def test_no_trace_callback_does_not_crash() -> None:
    """If emit_trace_event is not provided, orchestrator still works fine."""
    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply(
        {"opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"]}
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=None)
    result = orch.run()
    assert result["reply_count"] >= 1


# --- Edge case hardening tests ---


def test_discuss_with_target_not_in_phase_is_ignored() -> None:
    """DISCUSS_WITH targeting someone outside the phase is ignored; round-robin continues."""
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Need delivery.\nDISCUSS_WITH: opc-delivery-lead | outside-phase",
                "Final.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Research input."],
            "opc-delivery-lead": ["Should not be called."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert "opc-delivery-lead" not in called_ids
    assert "opc-research-lead" in called_ids


def test_discuss_with_invalid_employee_is_ignored() -> None:
    """DISCUSS_WITH targeting a completely invalid employee id is ignored."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Need ghost.\nDISCUSS_WITH: nonexistent-person | ???",
                "Final.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Input."],
        }
    )
    orch = _build_orchestrator(plan, gen, emit_trace_event=_emit)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert "nonexistent-person" not in called_ids
    assert "opc-research-lead" in called_ids


def test_global_turn_limit_emits_stop_event() -> None:
    """When global turn limit stops execution, remaining phases are not started."""
    trace_events: list[dict] = []

    def _emit(event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        trace_events.append({"type": event_type, "message": message, "metadata": metadata or {}})

    plan = _make_plan(
        [
            _phase("p1", "opc-product-lead", ["opc-research-lead"], max_turns=10),
            _phase("p2", "opc-engineering-lead", max_turns=10),
        ]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Go."] * 5,
            "opc-research-lead": ["Ok."] * 5,
            "opc-engineering-lead": ["Build."],
        }
    )
    orch = _build_orchestrator(plan, gen, global_turn_limit=3, emit_trace_event=_emit)
    orch.run()

    started_phases = [e["metadata"]["phase_id"] for e in trace_events if e["type"] == "phase_started"]
    assert "p1" in started_phases
    assert "p2" not in started_phases
