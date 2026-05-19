"""Tests for extended protocol parsing in _parse_structured_agent_reply."""

from app.openclaw.services import OpenClawGatewayAdapter


def _parse(text: str) -> dict:
    svc = OpenClawGatewayAdapter.__new__(OpenClawGatewayAdapter)
    return svc._parse_structured_agent_reply(text)


def test_parse_reply_with_phase_plan() -> None:
    text = (
        "My analysis.\n"
        "PHASE_PLAN:\n"
        "- phase: p1 | lead: opc-product-lead | with: opc-research-lead\n"
        "END_PHASE_PLAN\n"
        "HANDOFF: opc-product-lead | start"
    )
    result = _parse(text)
    assert "PHASE_PLAN:" not in result["reply_text"]
    assert "END_PHASE_PLAN" not in result["reply_text"]
    assert result["phase_plan_raw"] is not None
    assert "opc-product-lead" in result["phase_plan_raw"]
    assert "My analysis." in result["reply_text"]


def test_parse_reply_with_phase_complete() -> None:
    text = "Done with analysis.\nPHASE_COMPLETE: yes\nHANDOFF: none"
    result = _parse(text)
    assert result["phase_complete"] is True
    assert "PHASE_COMPLETE:" not in result["reply_text"]
    assert "Done with analysis." in result["reply_text"]


def test_parse_reply_with_phase_complete_no() -> None:
    text = "Still working.\nPHASE_COMPLETE: no"
    result = _parse(text)
    assert result["phase_complete"] is False


def test_parse_reply_with_discuss_with() -> None:
    text = "Need input.\nDISCUSS_WITH: opc-research-lead | feasibility check"
    result = _parse(text)
    assert result["discuss_with_target"] == "opc-research-lead"
    assert result["discuss_with_reason"] == "feasibility check"
    assert "DISCUSS_WITH:" not in result["reply_text"]


def test_parse_reply_with_discuss_with_no_reason() -> None:
    text = "DISCUSS_WITH: opc-quality-lead"
    result = _parse(text)
    assert result["discuss_with_target"] == "opc-quality-lead"
    assert result["discuss_with_reason"] is None


def test_parse_reply_mixed_old_and_new_protocol() -> None:
    text = (
        "Analysis.\n"
        "HANDOFF: opc-engineering-lead | tech design\n"
        "TURN_COMPLETE: no\n"
        "PHASE_COMPLETE: yes\n"
        "DISCUSS_WITH: opc-quality-lead | review"
    )
    result = _parse(text)
    assert result["handoff_targets"] == ["opc-engineering-lead"]
    assert result["handoff_reason"] == "tech design"
    assert result["turn_complete"] is False
    assert result["phase_complete"] is True
    assert result["discuss_with_target"] == "opc-quality-lead"
    assert result["discuss_with_reason"] == "review"


def test_parse_reply_no_phase_protocol() -> None:
    text = "Normal reply.\nHANDOFF: opc-product-lead | reason\nTURN_COMPLETE: yes"
    result = _parse(text)
    assert result["phase_plan_raw"] is None
    assert result["phase_complete"] is None
    assert result["discuss_with_target"] is None
    assert result["discuss_with_reason"] is None
    assert result["handoff_targets"] == ["opc-product-lead"]
    assert result["turn_complete"] is True
