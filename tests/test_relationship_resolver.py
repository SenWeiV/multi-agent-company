from __future__ import annotations

from app.company.models import CollaborationEdge, RoutingRule
from app.orchestration.models import (
    DiscussionPhase,
    DiscussionPlan,
    DiscussionRole,
    PhaseParticipant,
)
from app.orchestration.relationship_resolver import RelationshipResolver


def _edges() -> list[CollaborationEdge]:
    return [
        CollaborationEdge(from_employee="chief-of-staff", to_employee="product-lead", relation_type="delegates_to"),
        CollaborationEdge(from_employee="chief-of-staff", to_employee="research-lead", relation_type="delegates_to"),
        CollaborationEdge(from_employee="product-lead", to_employee="design-lead", relation_type="collaborates_with"),
        CollaborationEdge(from_employee="product-lead", to_employee="engineering-lead", relation_type="collaborates_with"),
        CollaborationEdge(from_employee="engineering-lead", to_employee="quality-lead", relation_type="delegates_to"),
        CollaborationEdge(from_employee="quality-lead", to_employee="chief-of-staff", relation_type="escalates_to"),
    ]


def _rules() -> list[RoutingRule]:
    return [
        RoutingRule(
            scenario="新需求",
            entry_point="chief-of-staff",
            typical_chain=["chief-of-staff", "product-lead", "engineering-lead"],
        ),
    ]


def _resolver() -> RelationshipResolver:
    return RelationshipResolver(edges=_edges(), rules=_rules())


class TestGetCollaborationWeight:
    def test_weight_delegates_to(self) -> None:
        r = _resolver()
        assert r.get_collaboration_weight("chief-of-staff", "product-lead") == 0.8

    def test_weight_collaborates_with(self) -> None:
        r = _resolver()
        assert r.get_collaboration_weight("product-lead", "design-lead") == 0.5

    def test_weight_escalates_to(self) -> None:
        r = _resolver()
        assert r.get_collaboration_weight("quality-lead", "chief-of-staff") == 1.0

    def test_weight_no_edge(self) -> None:
        r = _resolver()
        assert r.get_collaboration_weight("design-lead", "research-lead") == 0.0

    def test_weight_bidirectional(self) -> None:
        r = _resolver()
        assert r.get_collaboration_weight("product-lead", "design-lead") == 0.5
        assert r.get_collaboration_weight("design-lead", "product-lead") == 0.5


class TestRankParticipants:
    def test_rank_participants_by_weight(self) -> None:
        r = _resolver()
        # chief-of-staff → product-lead is delegates_to (0.8)
        # chief-of-staff → research-lead is delegates_to (0.8)
        # chief-of-staff → engineering-lead has no direct edge (0.0)
        ranked = r.rank_participants("chief-of-staff", ["engineering-lead", "product-lead", "research-lead"])
        assert ranked[0] in ("product-lead", "research-lead")
        assert ranked[2] == "engineering-lead"

    def test_rank_preserves_order_for_equal_weight(self) -> None:
        r = _resolver()
        # Both have 0.8 from chief-of-staff
        ranked = r.rank_participants("chief-of-staff", ["research-lead", "product-lead"])
        assert ranked == ["research-lead", "product-lead"]


class TestValidatePhasePlan:
    def test_validate_plan_warns_on_no_edge(self) -> None:
        r = _resolver()
        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="design-lead",
                participants=[PhaseParticipant(employee_id="research-lead", role=DiscussionRole.PARTICIPANT)],
            ),
        ])
        warnings = r.validate_phase_plan(plan)
        assert len(warnings) >= 1
        assert "research-lead" in warnings[0]

    def test_validate_plan_no_warning_for_connected(self) -> None:
        r = _resolver()
        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="product-lead",
                participants=[PhaseParticipant(employee_id="design-lead", role=DiscussionRole.PARTICIPANT)],
            ),
        ])
        warnings = r.validate_phase_plan(plan)
        assert len(warnings) == 0


class TestRelationshipContext:
    def test_relationship_context_generation(self) -> None:
        r = _resolver()
        phase = DiscussionPhase(
            phase_id="p1",
            title="需求分析",
            lead_id="product-lead",
            participants=[PhaseParticipant(employee_id="design-lead", role=DiscussionRole.PARTICIPANT)],
        )
        ctx = r.get_relationship_context("design-lead", phase)
        assert "product-lead" in ctx
        assert "collaborates_with" in ctx


class TestOrchestratorIntegration:
    def test_orchestrator_uses_resolver_for_speaker_order(self) -> None:
        from unittest.mock import MagicMock

        from app.orchestration.phase_orchestrator import PhaseOrchestrator

        r = _resolver()
        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="chief-of-staff",
                participants=[
                    PhaseParticipant(employee_id="engineering-lead", role=DiscussionRole.PARTICIPANT),
                    PhaseParticipant(employee_id="product-lead", role=DiscussionRole.PARTICIPANT),
                ],
                max_turns=5,
            ),
        ])

        call_order: list[str] = []

        def _gen(*, employee_id: str, **kwargs) -> MagicMock:
            call_order.append(employee_id)
            result = MagicMock()
            if employee_id == "chief-of-staff" and len([x for x in call_order if x == "chief-of-staff"]) >= 2:
                result.reply_text = "Done.\nPHASE_COMPLETE: yes"
            else:
                result.reply_text = "Input."
            return result

        def _send(*, employee_id: str, text: str) -> MagicMock:
            result = MagicMock()
            result.status = "sent"
            return result

        orch = PhaseOrchestrator(
            plan=plan,
            global_turn_limit=20,
            initial_visible_turn_count=0,
            generate_reply_fn=_gen,
            send_message_fn=_send,
            source_reply_text="Source.",
            valid_employee_ids={"chief-of-staff", "product-lead", "engineering-lead"},
            relationship_resolver=r,
        )
        orch.run()

        # chief-of-staff speaks first (lead), then product-lead (0.8 weight) before engineering-lead (0.0 weight)
        non_lead = [x for x in call_order if x != "chief-of-staff"]
        assert non_lead[0] == "product-lead"
        assert non_lead[1] == "engineering-lead"

    def test_orchestrator_without_resolver_preserves_old_behavior(self) -> None:
        from unittest.mock import MagicMock

        from app.orchestration.phase_orchestrator import PhaseOrchestrator

        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="chief-of-staff",
                participants=[
                    PhaseParticipant(employee_id="engineering-lead", role=DiscussionRole.PARTICIPANT),
                    PhaseParticipant(employee_id="product-lead", role=DiscussionRole.PARTICIPANT),
                ],
                max_turns=5,
            ),
        ])

        call_order: list[str] = []

        def _gen(*, employee_id: str, **kwargs) -> MagicMock:
            call_order.append(employee_id)
            result = MagicMock()
            if employee_id == "chief-of-staff" and len([x for x in call_order if x == "chief-of-staff"]) >= 2:
                result.reply_text = "Done.\nPHASE_COMPLETE: yes"
            else:
                result.reply_text = "Input."
            return result

        def _send(*, employee_id: str, text: str) -> MagicMock:
            result = MagicMock()
            result.status = "sent"
            return result

        orch = PhaseOrchestrator(
            plan=plan,
            global_turn_limit=20,
            initial_visible_turn_count=0,
            generate_reply_fn=_gen,
            send_message_fn=_send,
            source_reply_text="Source.",
            valid_employee_ids={"chief-of-staff", "product-lead", "engineering-lead"},
        )
        orch.run()

        # Without resolver, order follows list order: engineering-lead first
        non_lead = [x for x in call_order if x != "chief-of-staff"]
        assert non_lead[0] == "engineering-lead"
        assert non_lead[1] == "product-lead"
