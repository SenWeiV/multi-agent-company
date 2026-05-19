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


def _make_generate_reply(
    replies: dict[str, list[str]],
) -> Any:
    """Build a mock generate_reply that returns canned replies per employee_id."""
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
    source_employee_id: str | None = None,
) -> PhaseOrchestrator:
    return PhaseOrchestrator(
        plan=plan,
        global_turn_limit=global_turn_limit,
        initial_visible_turn_count=1,
        generate_reply_fn=generate_reply,
        send_message_fn=send_message or _make_send_message(),
        source_reply_text=source_reply_text,
        valid_employee_ids=valid_employee_ids
        or {"opc-chief-of-staff", "opc-product-lead", "opc-research-lead", "opc-engineering-lead", "opc-quality-lead", "opc-delivery-lead"},
        source_employee_id=source_employee_id,
    )


def test_single_phase_lead_only() -> None:
    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply(
        {"opc-product-lead": ["Product analysis.\nPHASE_COMPLETE: yes"]}
    )
    orch = _build_orchestrator(plan, gen)
    result = orch.run()

    assert result["reply_count"] >= 1
    assert gen.call_count == 1
    assert plan.phases[0].status == PhaseStatus.COMPLETED


def test_single_phase_lead_and_participant() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"], max_turns=10)]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Initial take.",
                "Final summary.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Research input."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    result = orch.run()

    assert result["reply_count"] >= 3
    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids[0] == "opc-product-lead"
    assert "opc-research-lead" in called_ids
    assert called_ids[-1] == "opc-product-lead"


def test_discuss_with_selects_target() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead", "opc-quality-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Need research.\nDISCUSS_WITH: opc-research-lead | feasibility",
                "Final.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Feasible."],
            "opc-quality-lead": ["Quality ok."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids[0] == "opc-product-lead"
    assert called_ids[1] == "opc-research-lead"


def test_handoff_within_phase_treated_as_discuss_with() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Check.\nHANDOFF: opc-research-lead | detail",
                "Done.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Input."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids[1] == "opc-research-lead"


def test_handoff_outside_phase_ignored() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"], max_turns=3)]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Check.\nHANDOFF: opc-delivery-lead | outside",
                "Done.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Input."],
            "opc-delivery-lead": ["Should not be called."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert "opc-delivery-lead" not in called_ids


def test_lead_gets_final_word() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Initial.",
                "Final.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Research."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids[-1] == "opc-product-lead"


def test_round_robin_fallback() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead", "opc-quality-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Start.",
                "Final.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Research."],
            "opc-quality-lead": ["Quality."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids[0] == "opc-product-lead"
    assert "opc-research-lead" in called_ids[1:3]
    assert "opc-quality-lead" in called_ids[1:3]


def test_phase_max_turns_forces_completion() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"], max_turns=2)]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Keep going."] * 5,
            "opc-research-lead": ["More."] * 5,
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    assert plan.phases[0].status == PhaseStatus.COMPLETED
    assert gen.call_count <= 2


def test_global_turn_limit_stops_all() -> None:
    plan = _make_plan(
        [
            _phase("p1", "opc-product-lead", ["opc-research-lead"], max_turns=10),
            _phase("p2", "opc-engineering-lead", max_turns=10),
        ]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Go.\nPHASE_COMPLETE: yes"],
            "opc-research-lead": ["Ok."],
            "opc-engineering-lead": ["Build."],
        }
    )
    orch = _build_orchestrator(plan, gen, global_turn_limit=2)
    orch.run()

    assert plan.phases[1].status != PhaseStatus.COMPLETED


def test_multi_phase_transition() -> None:
    plan = _make_plan(
        [
            _phase("p1", "opc-product-lead", max_turns=10),
            _phase("p2", "opc-engineering-lead", max_turns=10),
        ]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
            "opc-engineering-lead": ["Built.\nPHASE_COMPLETE: yes"],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    assert plan.phases[0].status == PhaseStatus.COMPLETED
    assert plan.phases[1].status == PhaseStatus.COMPLETED
    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids == ["opc-product-lead", "opc-engineering-lead"]


def test_phase_context_includes_prior_replies() -> None:
    plan = _make_plan(
        [_phase("p1", "opc-product-lead", ["opc-research-lead"])]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": [
                "Product analysis here.",
                "Final.\nPHASE_COMPLETE: yes",
            ],
            "opc-research-lead": ["Research input."],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    research_call = gen.call_args_list[1]
    phase_context = research_call.kwargs.get("phase_context", "")
    assert "Product analysis here." in phase_context


def test_phase_carry_over() -> None:
    plan = _make_plan(
        [
            _phase("p1", "opc-product-lead"),
            _phase("p2", "opc-engineering-lead"),
        ]
    )
    gen = _make_generate_reply(
        {
            "opc-product-lead": ["Phase 1 conclusion.\nPHASE_COMPLETE: yes"],
            "opc-engineering-lead": ["Engineering.\nPHASE_COMPLETE: yes"],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    eng_call = gen.call_args_list[1]
    phase_context = eng_call.kwargs.get("phase_context", "")
    assert "Phase 1 conclusion." in phase_context


def test_skip_phase_with_invalid_lead() -> None:
    plan = _make_plan(
        [
            _phase("p1", "nonexistent-lead"),
            _phase("p2", "opc-engineering-lead"),
        ]
    )
    gen = _make_generate_reply(
        {
            "opc-engineering-lead": ["Built.\nPHASE_COMPLETE: yes"],
        }
    )
    orch = _build_orchestrator(plan, gen)
    orch.run()

    assert plan.phases[0].status == PhaseStatus.SKIPPED
    assert plan.phases[1].status == PhaseStatus.COMPLETED


def test_reply_count_and_errors_returned() -> None:
    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply(
        {"opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"]}
    )
    orch = _build_orchestrator(plan, gen)
    result = orch.run()

    assert isinstance(result["reply_count"], int)
    assert isinstance(result["reply_errors"], list)
    assert result["reply_count"] >= 1


def test_auto_summary_appended_when_last_phase_not_source() -> None:
    plan = _make_plan([
        _phase("p1", "opc-product-lead"),
        _phase("p2", "opc-engineering-lead"),
    ])
    gen = _make_generate_reply({
        "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
        "opc-engineering-lead": ["Built.\nPHASE_COMPLETE: yes"],
        "opc-chief-of-staff": ["Summary conclusions.\nPHASE_COMPLETE: yes"],
    })
    orch = _build_orchestrator(plan, gen, source_employee_id="opc-chief-of-staff")
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids[-1] == "opc-chief-of-staff"


def test_auto_summary_skipped_when_last_phase_is_source() -> None:
    plan = _make_plan([
        _phase("p1", "opc-product-lead"),
        _phase("p2", "opc-chief-of-staff"),
    ])
    gen = _make_generate_reply({
        "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
        "opc-chief-of-staff": ["Summary.\nPHASE_COMPLETE: yes"],
    })
    orch = _build_orchestrator(plan, gen, source_employee_id="opc-chief-of-staff")
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert called_ids == ["opc-product-lead", "opc-chief-of-staff"]


def test_auto_summary_skipped_when_no_source_employee_id() -> None:
    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply({
        "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
    })
    orch = _build_orchestrator(plan, gen, source_employee_id=None)
    orch.run()

    assert gen.call_count == 1


def test_auto_summary_context_includes_summary_instructions() -> None:
    plan = _make_plan([_phase("p1", "opc-product-lead")])
    gen = _make_generate_reply({
        "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
        "opc-chief-of-staff": ["Summary.\nPHASE_COMPLETE: yes"],
    })
    orch = _build_orchestrator(plan, gen, source_employee_id="opc-chief-of-staff")
    orch.run()

    summary_call = gen.call_args_list[-1]
    phase_context = summary_call.kwargs.get("phase_context", "")
    assert "核心结论" in phase_context
    assert "下一步行动" in phase_context


def test_auto_summary_respects_global_turn_limit() -> None:
    plan = _make_plan([
        _phase("p1", "opc-product-lead"),
        _phase("p2", "opc-engineering-lead"),
    ])
    gen = _make_generate_reply({
        "opc-product-lead": ["Done.\nPHASE_COMPLETE: yes"],
        "opc-engineering-lead": ["Built.\nPHASE_COMPLETE: yes"],
        "opc-chief-of-staff": ["Should not be called."],
    })
    orch = _build_orchestrator(plan, gen, global_turn_limit=3, source_employee_id="opc-chief-of-staff")
    orch.run()

    called_ids = [c.kwargs["employee_id"] for c in gen.call_args_list]
    assert "opc-chief-of-staff" not in called_ids
