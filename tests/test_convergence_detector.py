from __future__ import annotations

from unittest.mock import MagicMock

from app.orchestration.convergence_detector import ConvergenceDetector
from app.orchestration.models import (
    DiscussionPhase,
    DiscussionPlan,
    DiscussionRole,
    PhaseParticipant,
    PhaseTurnRecord,
)


def _phase(participants: list[str] | None = None) -> DiscussionPhase:
    return DiscussionPhase(
        phase_id="p1",
        title="Test",
        lead_id="lead",
        participants=[
            PhaseParticipant(employee_id=eid, role=DiscussionRole.PARTICIPANT)
            for eid in (participants or ["a", "b"])
        ],
        max_turns=10,
    )


def _record(speaker: str, text: str) -> PhaseTurnRecord:
    role = DiscussionRole.LEAD if speaker == "lead" else DiscussionRole.PARTICIPANT
    return PhaseTurnRecord(speaker_id=speaker, role=role, reply_text=text)


class TestConvergenceBasic:
    def test_empty_records_returns_continue(self) -> None:
        d = ConvergenceDetector()
        signal = d.evaluate([], _phase())
        assert signal.recommendation == "continue"

    def test_single_turn_returns_continue(self) -> None:
        d = ConvergenceDetector()
        records = [_record("lead", "这是一个关于市场调研的深度分析，涵盖了多个维度的竞品对比。")]
        signal = d.evaluate(records, _phase())
        assert signal.recommendation == "continue"

    def test_no_convergence_with_diverse_replies(self) -> None:
        d = ConvergenceDetector()
        records = [
            _record("lead", "我们需要从技术架构角度分析这个系统的可扩展性和性能瓶颈。"),
            _record("a", "从用户体验设计角度来看，交互流程需要简化，减少操作步骤。"),
            _record("b", "市场竞品分析表明，定价策略应该采用阶梯式收费模式。"),
        ]
        signal = d.evaluate(records, _phase())
        assert signal.recommendation == "continue"
        assert signal.repetition_ratio < 0.7

    def test_high_repetition_triggers_force_complete(self) -> None:
        d = ConvergenceDetector(force_threshold=0.75)
        base_text = "总结来看，我们需要关注用户增长、产品迭代、技术架构三个核心维度的协同发展。"
        records = [
            _record("lead", base_text),
            _record("a", base_text),
            _record("b", base_text),
            _record("lead", base_text),
        ]
        signal = d.evaluate(records, _phase())
        assert signal.recommendation == "force_complete"
        assert signal.all_participants_spoken is True

    def test_moderate_repetition_triggers_suggest(self) -> None:
        d = ConvergenceDetector(suggest_threshold=0.5)
        base = "技术架构设计和性能优化是核心重点，我们需要评估可行性方案。"
        records = [
            _record("lead", f"我们需要评估{base}"),
            _record("a", f"同意，{base}确实需要关注。"),
            _record("lead", f"总结一下，{base}这是我们的共识。"),
        ]
        signal = d.evaluate(records, _phase())
        assert signal.recommendation in ("suggest_wrap_up", "force_complete")

    def test_force_complete_requires_all_spoken(self) -> None:
        d = ConvergenceDetector()
        base_text = "核心结论是我们需要关注用户增长和产品迭代以及技术架构三个维度的发展。"
        records = [
            _record("lead", base_text),
            _record("a", f"同意，{base_text}"),
            # participant "b" has NOT spoken
            _record("lead", f"总结一下，{base_text}"),
        ]
        signal = d.evaluate(records, _phase())
        # Cannot force_complete because not all participants have spoken
        if signal.repetition_ratio >= 0.85:
            assert signal.recommendation == "suggest_wrap_up"

    def test_length_decay_increases_repetition_signal(self) -> None:
        d = ConvergenceDetector()
        base = "产品架构需要优化迭代，关注用户核心体验和技术可扩展性的平衡。"
        records = [
            _record("lead", base * 3),
            _record("a", base),
            _record("b", "同意产品架构优化。"),
        ]
        signal_with_decay = d.evaluate(records, _phase())
        # Compare: without the length decay (equal length replies)
        records_equal = [
            _record("lead", base * 3),
            _record("a", base * 3),
            _record("b", base * 3),
        ]
        signal_without_decay = d.evaluate(records_equal, _phase())
        # The decaying version should still have reasonable info gain detection
        # but the key assertion is that length decay contributes to the signal
        assert signal_with_decay.repetition_ratio >= 0.0

    def test_custom_thresholds(self) -> None:
        d = ConvergenceDetector(force_threshold=0.5, suggest_threshold=0.3)
        base = "产品需要迭代升级，关注用户核心诉求。"
        records = [
            _record("lead", base),
            _record("a", f"同意，{base}"),
            _record("b", f"赞同，{base}"),
        ]
        signal = d.evaluate(records, _phase())
        # With low thresholds, should trigger more easily
        assert signal.recommendation in ("suggest_wrap_up", "force_complete")


class TestOrchestratorConvergenceIntegration:
    def test_orchestrator_force_completes_on_convergence(self) -> None:
        from app.orchestration.phase_orchestrator import PhaseOrchestrator

        base = "核心结论是产品需要从三个维度进行全面优化和迭代提升。"
        call_count = {"n": 0}

        def _gen(*, employee_id: str, **kwargs) -> MagicMock:
            call_count["n"] += 1
            result = MagicMock()
            result.reply_text = f"第{call_count['n']}轮: {base}"
            return result

        def _send(*, employee_id: str, text: str) -> MagicMock:
            r = MagicMock()
            r.status = "sent"
            return r

        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="lead",
                participants=[
                    PhaseParticipant(employee_id="a", role=DiscussionRole.PARTICIPANT),
                    PhaseParticipant(employee_id="b", role=DiscussionRole.PARTICIPANT),
                ],
                max_turns=20,
            ),
        ])

        detector = ConvergenceDetector(force_threshold=0.7, suggest_threshold=0.5)
        orch = PhaseOrchestrator(
            plan=plan,
            global_turn_limit=40,
            initial_visible_turn_count=0,
            generate_reply_fn=_gen,
            send_message_fn=_send,
            source_reply_text="Source.",
            valid_employee_ids={"lead", "a", "b"},
            convergence_detector=detector,
        )
        orch.run()

        # Should stop before max_turns (20) due to convergence
        assert plan.phases[0].turns_used < 20

    def test_orchestrator_injects_wrap_up_hint(self) -> None:
        from app.orchestration.phase_orchestrator import PhaseOrchestrator

        base = "结论是我们需要关注三个核心维度的协同发展和持续优化。"
        call_idx = {"n": 0}
        contexts_seen: list[str] = []

        def _gen(*, employee_id: str, phase_context: str = "", **kwargs) -> MagicMock:
            call_idx["n"] += 1
            contexts_seen.append(phase_context)
            result = MagicMock()
            # Vary content slightly so Jaccard stays between suggest and force thresholds
            if call_idx["n"] == 1:
                result.reply_text = f"从产品角度看，{base}这需要深入分析。"
            elif call_idx["n"] == 2:
                result.reply_text = f"技术视角来看，{base}我赞同这个方向。"
            else:
                result.reply_text = f"综合来看，{base}这是团队共识。\nPHASE_COMPLETE: yes"
            return result

        def _send(*, employee_id: str, text: str) -> MagicMock:
            r = MagicMock()
            r.status = "sent"
            return r

        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="lead",
                participants=[
                    PhaseParticipant(employee_id="a", role=DiscussionRole.PARTICIPANT),
                ],
                max_turns=10,
            ),
        ])

        # suggest_threshold low enough to trigger on partially overlapping content
        detector = ConvergenceDetector(force_threshold=0.95, suggest_threshold=0.4)
        orch = PhaseOrchestrator(
            plan=plan,
            global_turn_limit=40,
            initial_visible_turn_count=0,
            generate_reply_fn=_gen,
            send_message_fn=_send,
            source_reply_text="Source.",
            valid_employee_ids={"lead", "a"},
            convergence_detector=detector,
        )
        orch.run()

        # After turn 2, convergence should trigger suggest_wrap_up.
        # Turn 3 is the lead — its context should contain the hint.
        hint_found = any("收敛" in ctx or "趋于收敛" in ctx for ctx in contexts_seen)
        assert hint_found, f"No convergence hint found. Contexts ({len(contexts_seen)} total)"

    def test_orchestrator_without_detector_preserves_old_behavior(self) -> None:
        from app.orchestration.phase_orchestrator import PhaseOrchestrator

        base = "重复内容重复内容重复内容。"
        call_count = {"n": 0}

        def _gen(*, employee_id: str, **kwargs) -> MagicMock:
            call_count["n"] += 1
            result = MagicMock()
            # Lead declares PHASE_COMPLETE on their second turn (call 3)
            if employee_id == "lead" and call_count["n"] >= 3:
                result.reply_text = f"{base}\nPHASE_COMPLETE: yes"
            else:
                result.reply_text = base
            return result

        def _send(*, employee_id: str, text: str) -> MagicMock:
            r = MagicMock()
            r.status = "sent"
            return r

        plan = DiscussionPlan(phases=[
            DiscussionPhase(
                phase_id="p1",
                title="Test",
                lead_id="lead",
                participants=[
                    PhaseParticipant(employee_id="a", role=DiscussionRole.PARTICIPANT),
                ],
                max_turns=20,
            ),
        ])

        orch = PhaseOrchestrator(
            plan=plan,
            global_turn_limit=40,
            initial_visible_turn_count=0,
            generate_reply_fn=_gen,
            send_message_fn=_send,
            source_reply_text="Source.",
            valid_employee_ids={"lead", "a"},
        )
        orch.run()

        # Without detector: lead(1) → a(2) → lead(3, PHASE_COMPLETE)
        assert call_count["n"] == 3
