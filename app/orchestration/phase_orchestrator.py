from __future__ import annotations

import logging
from typing import Any, Callable

from app.orchestration.convergence_detector import ConvergenceDetector
from app.orchestration.models import (
    DiscussionPlan,
    DiscussionPhase,
    DiscussionRole,
    PhaseStatus,
    PhaseTurnRecord,
)
from app.orchestration.plan_parser import parse_phase_signals, strip_phase_protocol_lines
from app.orchestration.relationship_resolver import RelationshipResolver

logger = logging.getLogger(__name__)


class PhaseOrchestrator:
    def __init__(
        self,
        *,
        plan: DiscussionPlan,
        global_turn_limit: int,
        initial_visible_turn_count: int,
        generate_reply_fn: Callable[..., Any],
        send_message_fn: Callable[..., Any],
        source_reply_text: str,
        valid_employee_ids: set[str],
        source_employee_id: str | None = None,
        emit_trace_event: Callable[..., None] | None = None,
        relationship_resolver: RelationshipResolver | None = None,
        convergence_detector: ConvergenceDetector | None = None,
    ) -> None:
        self._plan = plan
        self._global_turn_limit = global_turn_limit
        self._visible_turn_count = initial_visible_turn_count
        self._generate_reply = generate_reply_fn
        self._send_message = send_message_fn
        self._source_reply_text = source_reply_text
        self._valid_employee_ids = valid_employee_ids
        self._source_employee_id = source_employee_id
        self._emit_trace_event = emit_trace_event
        self._relationship_resolver = relationship_resolver
        self._convergence_detector = convergence_detector

        self.reply_count = 0
        self.reply_errors: list[str] = []

        self._phase_summaries: list[str] = []

    def _emit(self, event_type: str, message: str, metadata: dict[str, str] | None = None) -> None:
        if self._emit_trace_event is not None:
            self._emit_trace_event(event_type, message, metadata)

    def run(self) -> dict[str, Any]:
        logger.info("PhaseOrchestrator.run() starting with %d phases", len(self._plan.phases))
        self._enforce_summary_phase_constraints()
        for phase in self._plan.phases:
            if self._visible_turn_count >= self._global_turn_limit:
                break
            if phase.lead_id not in self._valid_employee_ids:
                phase.status = PhaseStatus.SKIPPED
                logger.warning("Skipping phase %s: invalid lead %s", phase.phase_id, phase.lead_id)
                self._emit(
                    "phase_skipped",
                    f"Skipped phase {phase.phase_id}: invalid lead {phase.lead_id}",
                    {"phase_id": phase.phase_id, "lead_id": phase.lead_id},
                )
                continue
            self._execute_phase(phase)

        self._maybe_auto_summary()

        return {
            "reply_count": self.reply_count,
            "reply_errors": self.reply_errors,
        }

    def _enforce_summary_phase_constraints(self) -> None:
        if not self._plan.phases:
            return
        last_phase = self._plan.phases[-1]
        summary_keywords = {"summary", "总结", "结论", "wrap-up", "wrapup"}
        is_summary = any(kw in (last_phase.phase_id or "").lower() or kw in (last_phase.title or "").lower() for kw in summary_keywords)
        if is_summary and last_phase.lead_id == self._source_employee_id:
            if last_phase.participants:
                logger.info("Enforcing summary phase constraint: removing participants from phase %s", last_phase.phase_id)
                last_phase.participants = []
            if last_phase.max_turns > 2:
                last_phase.max_turns = 2

    def _execute_phase(self, phase: DiscussionPhase) -> None:
        phase.status = PhaseStatus.ACTIVE
        turn_records: list[PhaseTurnRecord] = []
        participant_spoken: set[str] = set()

        prior_context = self._build_carry_over_context()
        logger.info(
            "Executing phase %s (lead=%s, participants=%s, max_turns=%d)",
            phase.phase_id, phase.lead_id,
            [p.employee_id for p in phase.participants], phase.max_turns,
        )

        self._emit(
            "phase_started",
            f"Phase {phase.phase_id} started (lead: {phase.lead_id})",
            {"phase_id": phase.phase_id, "lead_id": phase.lead_id},
        )

        completed_by_signal = False
        convergence_hint_active = False

        while phase.turns_used < phase.max_turns:
            if self._visible_turn_count >= self._global_turn_limit:
                break

            speaker_id = self._select_next_speaker(
                phase, turn_records, participant_spoken
            )
            if speaker_id is None:
                break

            role = (
                DiscussionRole.LEAD
                if speaker_id == phase.lead_id
                else DiscussionRole.PARTICIPANT
            )

            phase_context = self._build_phase_turn_context(
                phase, speaker_id, role, turn_records, prior_context,
                convergence_hint=convergence_hint_active and speaker_id == phase.lead_id,
            )

            logger.info("Phase %s turn %d: generating reply for %s (%s)", phase.phase_id, phase.turns_used + 1, speaker_id, role.value)
            result = self._generate_reply(
                employee_id=speaker_id,
                phase_context=phase_context,
            )

            visible_text = strip_phase_protocol_lines(result.reply_text)
            logger.info("Phase %s: %s replied (%d chars visible)", phase.phase_id, speaker_id, len(visible_text))

            send_result = self._send_message(
                employee_id=speaker_id,
                text=visible_text,
            )
            if getattr(send_result, "status", "sent") in {"sent", "deduplicated"}:
                self.reply_count += 1
            else:
                self.reply_errors.append(
                    getattr(send_result, "error_detail", None) or "send failed"
                )

            turn_records.append(
                PhaseTurnRecord(
                    speaker_id=speaker_id,
                    role=role,
                    reply_text=visible_text,
                )
            )
            if speaker_id != phase.lead_id:
                participant_spoken.add(speaker_id)

            phase.turns_used += 1
            self._visible_turn_count += 1

            self._emit(
                "phase_speaker_turn",
                f"{speaker_id} spoke in phase {phase.phase_id} (turn {phase.turns_used})",
                {
                    "phase_id": phase.phase_id,
                    "speaker_id": speaker_id,
                    "role": role.value,
                    "turn_number": str(phase.turns_used),
                },
            )

            signal = parse_phase_signals(result.reply_text)

            if signal.phase_complete and speaker_id == phase.lead_id:
                phase.status = PhaseStatus.COMPLETED
                self._phase_summaries.append(
                    self._summarize_phase(phase, turn_records)
                )
                self._emit(
                    "phase_completed",
                    f"Phase {phase.phase_id} completed by lead signal",
                    {"phase_id": phase.phase_id, "turns_used": str(phase.turns_used)},
                )
                completed_by_signal = True
                return

            if signal.next_speaker and signal.next_speaker != speaker_id:
                if self._is_in_phase(signal.next_speaker, phase):
                    self._push_next_speaker(phase, signal.next_speaker, turn_records)
                else:
                    logger.warning(
                        "DISCUSS_WITH target %s not in phase %s participants; ignoring",
                        signal.next_speaker,
                        phase.phase_id,
                    )

            handoff_target = self._extract_handoff_from_reply(result)
            if handoff_target and handoff_target != speaker_id:
                if self._is_in_phase(handoff_target, phase):
                    self._push_next_speaker(phase, handoff_target, turn_records)

            if self._convergence_detector is not None:
                conv_signal = self._convergence_detector.evaluate(turn_records, phase)
                if conv_signal.recommendation == "force_complete":
                    phase.status = PhaseStatus.COMPLETED
                    self._phase_summaries.append(self._summarize_phase(phase, turn_records))
                    self._emit(
                        "phase_convergence_forced",
                        f"Phase {phase.phase_id} force-completed by convergence detector",
                        {"phase_id": phase.phase_id, "turns_used": str(phase.turns_used), "repetition_ratio": f"{conv_signal.repetition_ratio:.2f}"},
                    )
                    completed_by_signal = True
                    return
                elif conv_signal.recommendation == "suggest_wrap_up":
                    convergence_hint_active = True

        phase.status = PhaseStatus.COMPLETED
        self._phase_summaries.append(self._summarize_phase(phase, turn_records))
        if not completed_by_signal:
            self._emit(
                "phase_forced_completion",
                f"Phase {phase.phase_id} force-completed at max_turns ({phase.turns_used})",
                {"phase_id": phase.phase_id, "turns_used": str(phase.turns_used)},
            )

    def _select_next_speaker(
        self,
        phase: DiscussionPhase,
        turn_records: list[PhaseTurnRecord],
        participant_spoken: set[str],
    ) -> str | None:
        if hasattr(phase, "_next_speaker_override") and phase._next_speaker_override:  # type: ignore[attr-defined]
            speaker = phase._next_speaker_override  # type: ignore[attr-defined]
            phase._next_speaker_override = None  # type: ignore[attr-defined]
            return speaker

        if not turn_records:
            return phase.lead_id

        all_participants = [p.employee_id for p in phase.participants]
        unspoken = [eid for eid in all_participants if eid not in participant_spoken]

        if unspoken:
            if self._relationship_resolver is not None:
                unspoken = self._relationship_resolver.rank_participants(phase.lead_id, unspoken)
            return unspoken[0]

        last_speaker = turn_records[-1].speaker_id
        if last_speaker != phase.lead_id:
            return phase.lead_id

        return None

    def _push_next_speaker(
        self,
        phase: DiscussionPhase,
        speaker_id: str,
        turn_records: list[PhaseTurnRecord],
    ) -> None:
        phase._next_speaker_override = speaker_id  # type: ignore[attr-defined]

    def _is_in_phase(self, employee_id: str, phase: DiscussionPhase) -> bool:
        if employee_id == phase.lead_id:
            return True
        return any(p.employee_id == employee_id for p in phase.participants)

    def _extract_handoff_from_reply(self, result: Any) -> str | None:
        text = getattr(result, "reply_text", "")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("HANDOFF:"):
                payload = stripped.split(":", 1)[1].strip()
                if payload and payload.lower() != "none":
                    target = payload.split("|")[0].strip().split(",")[0].strip()
                    return target if target else None
        return None

    def _build_phase_turn_context(
        self,
        phase: DiscussionPhase,
        speaker_id: str,
        role: DiscussionRole,
        turn_records: list[PhaseTurnRecord],
        prior_phase_context: str,
        convergence_hint: bool = False,
    ) -> str:
        parts: list[str] = []

        if prior_phase_context:
            parts.append(f"=== 前序阶段讨论摘要 ===\n{prior_phase_context}")

        parts.append(f"=== 来源回复 ===\n{self._source_reply_text}")

        if role == DiscussionRole.LEAD:
            participant_names = ", ".join(p.employee_id for p in phase.participants)
            if phase.phase_id == "auto-summary":
                parts.append(
                    "你是最初规划本次讨论的主持人。所有讨论阶段已完成。\n"
                    "请综合各阶段的讨论成果，给出：\n"
                    "1. 本次讨论的核心结论\n"
                    "2. 已达成的共识\n"
                    "3. 尚需解决的问题\n"
                    "4. 建议的下一步行动"
                )
            else:
                parts.append(
                    f"你是本阶段的主持人（lead）。阶段目标：{phase.title}。\n"
                    f"参与者：{participant_names or 'none'}。\n"
                    f"你可以用 DISCUSS_WITH: employee-id | reason 邀请特定同事讨论。\n"
                    f"当阶段目标达成时，追加 PHASE_COMPLETE: yes。\n"
                    f"阶段最大轮数：{phase.max_turns}，当前轮数：{phase.turns_used}。"
                )
        else:
            parts.append(
                f"你是本阶段的参与者。阶段主持人是 {phase.lead_id}。阶段目标：{phase.title}。\n"
                f"请围绕阶段目标发表你的专业观点。如需进一步讨论，可用 DISCUSS_WITH: employee-id | reason。\n"
                f"不要声明 PHASE_COMPLETE——这是主持人的职责。"
            )

        if turn_records:
            history_lines = []
            for rec in turn_records:
                history_lines.append(f"[{rec.speaker_id} ({rec.role.value})]: {rec.reply_text}")
            parts.append(f"=== 本阶段讨论记录 ===\n" + "\n".join(history_lines))

        if self._relationship_resolver is not None:
            rel_ctx = self._relationship_resolver.get_relationship_context(speaker_id, phase)
            if rel_ctx:
                parts.append(rel_ctx)

        if convergence_hint:
            parts.append(
                "=== 收敛提示 ===\n"
                "系统检测到本阶段讨论已趋于收敛（观点重复度较高）。"
                "建议总结当前讨论要点并声明 PHASE_COMPLETE: yes 结束本阶段。"
            )

        return "\n\n".join(parts)

    def _build_carry_over_context(self) -> str:
        return "\n\n".join(self._phase_summaries)

    def _maybe_auto_summary(self) -> None:
        if not self._source_employee_id:
            return
        if self._visible_turn_count >= self._global_turn_limit:
            return
        if self._source_employee_id not in self._valid_employee_ids:
            return

        completed_phases = [p for p in self._plan.phases if p.status == PhaseStatus.COMPLETED]
        if not completed_phases:
            return
        if completed_phases[-1].lead_id == self._source_employee_id:
            return

        logger.info("Auto-appending summary phase for %s", self._source_employee_id)
        summary_phase = DiscussionPhase(
            phase_id="auto-summary",
            title="总结与结论",
            lead_id=self._source_employee_id,
            participants=[],
            max_turns=2,
        )
        self._emit(
            "auto_summary_phase",
            f"Auto-appending summary phase led by {self._source_employee_id}",
            {"source_employee_id": self._source_employee_id},
        )
        self._execute_phase(summary_phase)

    def _summarize_phase(
        self,
        phase: DiscussionPhase,
        turn_records: list[PhaseTurnRecord],
    ) -> str:
        if not turn_records:
            return f"Phase {phase.phase_id}: (no discussion)"
        last_reply = turn_records[-1].reply_text
        return (
            f"Phase {phase.phase_id} ({phase.title}) — "
            f"Lead: {phase.lead_id}, Turns: {phase.turns_used}\n"
            f"Final: {last_reply[:500]}"
        )
