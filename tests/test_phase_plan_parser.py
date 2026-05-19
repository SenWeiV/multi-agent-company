from app.orchestration.models import DiscussionRole
from app.orchestration.plan_parser import (
    parse_phase_plan,
    parse_phase_signals,
    strip_phase_protocol_lines,
)

VALID_EMPLOYEES = {
    "opc-product-lead",
    "opc-research-lead",
    "opc-engineering-lead",
    "opc-quality-lead",
    "opc-delivery-lead",
    "opc-chief-of-staff",
}


def test_parse_valid_phase_plan() -> None:
    text = (
        "Some analysis here.\n"
        "PHASE_PLAN:\n"
        "- phase: product-definition | lead: opc-product-lead | with: opc-research-lead | max_turns: 10\n"
        "- phase: technical-design | lead: opc-engineering-lead | with: opc-product-lead, opc-quality-lead | max_turns: 8\n"
        "- phase: review | lead: opc-delivery-lead | with: opc-quality-lead | max_turns: 6\n"
        "END_PHASE_PLAN\n"
        "HANDOFF: opc-product-lead | start"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert len(plan.phases) == 3

    p1 = plan.phases[0]
    assert p1.phase_id == "product-definition"
    assert p1.lead_id == "opc-product-lead"
    assert len(p1.participants) == 1
    assert p1.participants[0].employee_id == "opc-research-lead"
    assert p1.participants[0].role == DiscussionRole.PARTICIPANT
    assert p1.max_turns == 10

    p2 = plan.phases[1]
    assert p2.lead_id == "opc-engineering-lead"
    assert len(p2.participants) == 2
    assert p2.max_turns == 8

    p3 = plan.phases[2]
    assert p3.lead_id == "opc-delivery-lead"
    assert p3.max_turns == 6


def test_parse_phase_plan_missing_end_marker() -> None:
    text = (
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: opc-product-lead | with: opc-research-lead\n"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None


def test_parse_phase_plan_invalid_lead() -> None:
    text = (
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: nonexistent-agent | with: opc-research-lead\n"
        "- phase: p2 | lead: opc-engineering-lead | with: opc-quality-lead\n"
        "END_PHASE_PLAN\n"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert len(plan.phases) == 1
    assert plan.phases[0].lead_id == "opc-engineering-lead"


def test_parse_phase_plan_invalid_participant() -> None:
    text = (
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: opc-product-lead | with: opc-research-lead, invalid-agent\n"
        "END_PHASE_PLAN\n"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert len(plan.phases[0].participants) == 1
    assert plan.phases[0].participants[0].employee_id == "opc-research-lead"


def test_parse_phase_plan_no_valid_phases() -> None:
    text = (
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: bad-lead | with: bad-participant\n"
        "END_PHASE_PLAN\n"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None


def test_parse_phase_plan_empty_input() -> None:
    plan = parse_phase_plan("Just a normal reply.", valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None


def test_parse_phase_plan_max_turns_default() -> None:
    text = (
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: opc-product-lead | with: opc-research-lead\n"
        "END_PHASE_PLAN\n"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert plan.phases[0].max_turns == 10


def test_parse_phase_plan_no_participants() -> None:
    text = (
        "PHASE_PLAN:\n"
        "- phase: solo | lead: opc-product-lead\n"
        "END_PHASE_PLAN\n"
    )
    plan = parse_phase_plan(text, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert plan.phases[0].participants == []


def test_parse_phase_signals_complete_yes() -> None:
    text = "Some reply.\nPHASE_COMPLETE: yes\nHANDOFF: none"
    signal = parse_phase_signals(text)
    assert signal.phase_complete is True


def test_parse_phase_signals_complete_no() -> None:
    text = "Some reply.\nPHASE_COMPLETE: no"
    signal = parse_phase_signals(text)
    assert signal.phase_complete is False


def test_parse_phase_signals_discuss_with() -> None:
    text = "I think we need input.\nDISCUSS_WITH: opc-research-lead | need feasibility check"
    signal = parse_phase_signals(text)
    assert signal.next_speaker == "opc-research-lead"
    assert signal.reason == "need feasibility check"


def test_parse_phase_signals_discuss_with_no_reason() -> None:
    text = "DISCUSS_WITH: opc-quality-lead"
    signal = parse_phase_signals(text)
    assert signal.next_speaker == "opc-quality-lead"
    assert signal.reason is None


def test_parse_phase_signals_no_signals() -> None:
    text = "Just a normal reply with no protocol."
    signal = parse_phase_signals(text)
    assert signal.phase_complete is False
    assert signal.next_speaker is None


def test_strip_phase_protocol_lines() -> None:
    text = (
        "My analysis.\n"
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: opc-product-lead | with: opc-research-lead\n"
        "END_PHASE_PLAN\n"
        "PHASE_COMPLETE: yes\n"
        "DISCUSS_WITH: opc-research-lead | reason\n"
        "Conclusion."
    )
    stripped = strip_phase_protocol_lines(text)
    assert "PHASE_PLAN:" not in stripped
    assert "END_PHASE_PLAN" not in stripped
    assert "PHASE_COMPLETE:" not in stripped
    assert "DISCUSS_WITH:" not in stripped
    assert "My analysis." in stripped
    assert "Conclusion." in stripped


def test_strip_preserves_handoff_and_turn_complete() -> None:
    text = (
        "My reply.\n"
        "HANDOFF: opc-product-lead | reason\n"
        "TURN_COMPLETE: yes\n"
        "PHASE_COMPLETE: yes"
    )
    stripped = strip_phase_protocol_lines(text)
    assert "HANDOFF:" in stripped
    assert "TURN_COMPLETE:" in stripped
    assert "PHASE_COMPLETE:" not in stripped
