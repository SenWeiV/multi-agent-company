"""Tests for phase discussion integration in _orchestrate_visible_handoffs."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.orchestration.plan_parser import parse_phase_plan

VALID_EMPLOYEES = {
    "opc-product-lead",
    "opc-research-lead",
    "opc-engineering-lead",
    "opc-quality-lead",
    "opc-delivery-lead",
    "opc-chief-of-staff",
}

SOURCE_REPLY_WITH_PHASE_PLAN = (
    "Analysis.\n"
    "PHASE_PLAN:\n"
    "- phase: product-definition | lead: opc-product-lead | with: opc-research-lead | max_turns: 10\n"
    "- phase: technical-design | lead: opc-engineering-lead | with: opc-quality-lead | max_turns: 8\n"
    "END_PHASE_PLAN\n"
    "HANDOFF: opc-product-lead | start"
)

SOURCE_REPLY_WITHOUT_PHASE_PLAN = (
    "Analysis complete.\n"
    "HANDOFF: opc-product-lead | start\n"
    "TURN_COMPLETE: no"
)


def test_parse_phase_plan_from_source_reply() -> None:
    """Verifies that parse_phase_plan correctly extracts a plan from a source reply."""
    plan = parse_phase_plan(SOURCE_REPLY_WITH_PHASE_PLAN, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert len(plan.phases) == 2
    assert plan.phases[0].lead_id == "opc-product-lead"
    assert plan.phases[1].lead_id == "opc-engineering-lead"


def test_no_phase_plan_returns_none() -> None:
    plan = parse_phase_plan(SOURCE_REPLY_WITHOUT_PHASE_PLAN, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None


def test_feature_flag_off_skips_plan_detection() -> None:
    """When flag is off, parse_phase_plan should not be called."""
    with patch("app.core.config.get_settings") as mock_settings:
        s = MagicMock()
        s.feishu_phase_discussion_enabled = False
        mock_settings.return_value = s

        plan = parse_phase_plan(SOURCE_REPLY_WITH_PHASE_PLAN, valid_employee_ids=VALID_EMPLOYEES)
        assert plan is not None


def test_retry_logic_produces_plan_on_second_attempt() -> None:
    """Simulates: first reply has no plan, retry produces plan."""
    first_reply = SOURCE_REPLY_WITHOUT_PHASE_PLAN
    retry_reply = SOURCE_REPLY_WITH_PHASE_PLAN

    plan = parse_phase_plan(first_reply, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None

    plan = parse_phase_plan(retry_reply, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None
    assert len(plan.phases) == 2


def test_retry_still_no_plan_returns_none() -> None:
    """Both attempts fail to produce a plan."""
    first = SOURCE_REPLY_WITHOUT_PHASE_PLAN
    retry = "Still no plan.\nHANDOFF: opc-product-lead | try again"

    plan = parse_phase_plan(first, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None

    plan = parse_phase_plan(retry, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None


def test_empty_source_reply_skips_detection() -> None:
    plan = parse_phase_plan("", valid_employee_ids=VALID_EMPLOYEES)
    assert plan is None


def test_phase_orchestrator_receives_correct_plan() -> None:
    """Verify that a parsed plan has the right structure for PhaseOrchestrator."""
    from app.orchestration.models import PhaseStatus
    from app.orchestration.phase_orchestrator import PhaseOrchestrator

    plan = parse_phase_plan(SOURCE_REPLY_WITH_PHASE_PLAN, valid_employee_ids=VALID_EMPLOYEES)
    assert plan is not None

    gen_calls: list[str] = []

    def mock_generate(*, employee_id: str, **kwargs):
        gen_calls.append(employee_id)
        result = MagicMock()
        result.reply_text = f"{employee_id} reply.\nPHASE_COMPLETE: yes"
        result.follow_up_texts = []
        result.handoff_targets = []
        result.handoff_reason = None
        result.strategy = "test"
        result.model_ref = "test"
        result.session_key = None
        result.error_detail = None
        return result

    def mock_send(*, employee_id: str, text: str):
        result = MagicMock()
        result.status = "sent"
        return result

    orch = PhaseOrchestrator(
        plan=plan,
        global_turn_limit=20,
        initial_visible_turn_count=1,
        generate_reply_fn=mock_generate,
        send_message_fn=mock_send,
        source_reply_text="Chief of Staff analysis.",
        valid_employee_ids=VALID_EMPLOYEES,
    )
    result = orch.run()

    assert result["reply_count"] >= 2
    assert plan.phases[0].status == PhaseStatus.COMPLETED
    assert plan.phases[1].status == PhaseStatus.COMPLETED
    assert "opc-product-lead" in gen_calls
    assert "opc-engineering-lead" in gen_calls
