from __future__ import annotations

from uuid import uuid4

from app.control_plane.models import RunEvent, RunTraceStatus, TaskGraphStatus
from app.control_plane.services import get_control_plane_service
from app.governance.models import (
    EscalationRequest,
    EscalationResult,
    EscalationSummary,
    OverrideDecision,
    OverrideRecoveryRequest,
    OverrideRecoveryResult,
)
from app.memory.services import get_memory_service
from app.store import ModelStore, build_model_store


class GovernanceService:
    def __init__(
        self,
        override_store: ModelStore[OverrideDecision],
        escalation_store: ModelStore[EscalationSummary],
    ) -> None:
        self._override_decisions = override_store
        self._escalations = escalation_store

    def override_recovery(self, request: OverrideRecoveryRequest) -> OverrideRecoveryResult:
        control_plane = get_control_plane_service()
        checkpoint = (
            control_plane.get_checkpoint(request.checkpoint_id)
            if request.checkpoint_id
            else control_plane.get_latest_checkpoint_for_ticket(request.work_ticket_id)
        )
        if checkpoint is None:
            raise ValueError("override_recovery requires an existing checkpoint")

        supersede_refs = control_plane.collect_supersede_refs(request.work_ticket_id, checkpoint.checkpoint_id)
        restored_checkpoint, work_ticket, task_graph, run_trace = control_plane.restore_checkpoint(
            checkpoint.checkpoint_id
        )
        decision_id = f"od-{uuid4().hex[:8]}"
        superseded_checkpoint = control_plane.mark_checkpoint_superseded(checkpoint.checkpoint_id, decision_id)
        work_ticket = control_plane.set_work_ticket_status(work_ticket.ticket_id, "override_restored")
        work_ticket = control_plane.set_work_ticket_supersede_refs(work_ticket.ticket_id, supersede_refs)
        run_trace = control_plane.append_run_trace_event(
            run_trace.runtrace_id,
            RunEvent(
                event_type="override_decision_recorded",
                message="Override recovery executed against the selected checkpoint.",
                metadata={
                    "checkpoint_id": restored_checkpoint.checkpoint_id,
                    "new_direction": request.new_direction,
                    "target": request.target,
                    "supersede_ref_count": str(len(supersede_refs)),
                },
            ),
            status=RunTraceStatus.ROUTED,
        )

        decision = OverrideDecision(
            decision_id=decision_id,
            work_ticket_ref=work_ticket.ticket_id,
            target=request.target,
            new_direction=request.new_direction,
            rollback_ref=restored_checkpoint.checkpoint_id,
            supersede_refs=supersede_refs,
            notes=request.summary,
            created_by=request.created_by,
        )
        decision = self._override_decisions.save(decision)
        get_memory_service().mark_superseded(restored_checkpoint.memory_refs, decision.decision_id)
        memory_records = get_memory_service().create_override_memories(
            work_ticket=work_ticket,
            run_trace=run_trace,
            checkpoint=superseded_checkpoint,
            new_direction=request.new_direction,
            supersede_refs=supersede_refs,
        )
        for memory_record in memory_records:
            superseded_checkpoint = control_plane.attach_memory_to_checkpoint(
                superseded_checkpoint.checkpoint_id,
                memory_record.memory_id,
            )

        return OverrideRecoveryResult(
            override_decision=decision,
            checkpoint=superseded_checkpoint,
            work_ticket=work_ticket,
            run_trace=run_trace,
            task_graph=task_graph,
        )

    def escalate(self, request: EscalationRequest) -> EscalationResult:
        control_plane = get_control_plane_service()
        work_ticket = control_plane.get_required_work_ticket(request.work_ticket_id)
        run_trace = control_plane.get_required_run_trace(work_ticket.runtrace_ref or "")
        checkpoint = (
            control_plane.get_checkpoint(request.checkpoint_id)
            if request.checkpoint_id
            else control_plane.get_latest_checkpoint_for_ticket(request.work_ticket_id)
        )
        task_graph = control_plane.get_task_graph(work_ticket.taskgraph_ref) if work_ticket.taskgraph_ref else None

        summary = EscalationSummary(
            escalation_id=f"es-{uuid4().hex[:8]}",
            work_ticket_ref=work_ticket.ticket_id,
            reason=request.reason,
            conflict_points=request.conflict_points,
            risk_notes=request.risk_notes,
            suggested_actions=request.suggested_actions,
            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
            created_by=request.created_by,
        )
        summary = self._escalations.save(summary)

        work_ticket = control_plane.set_work_ticket_status(work_ticket.ticket_id, "escalated")
        if task_graph is not None:
            task_graph = control_plane.set_task_graph_status(task_graph.taskgraph_id, TaskGraphStatus.ESCALATED)
        run_trace = control_plane.append_run_trace_event(
            run_trace.runtrace_id,
            RunEvent(
                event_type="escalation_recorded",
                message="Work ticket escalated for executive handling.",
                metadata={
                    "escalation_id": summary.escalation_id,
                    "reason": request.reason,
                },
            ),
            status=RunTraceStatus.ESCALATED,
        )
        memory_records = get_memory_service().create_escalation_memories(
            work_ticket=work_ticket,
            run_trace=run_trace,
            checkpoint=checkpoint,
            reason=request.reason,
            risk_notes=request.risk_notes,
        )
        if checkpoint is not None:
            for memory_record in memory_records:
                checkpoint = control_plane.attach_memory_to_checkpoint(checkpoint.checkpoint_id, memory_record.memory_id)

        return EscalationResult(
            escalation_summary=summary,
            checkpoint=checkpoint,
            work_ticket=work_ticket,
            run_trace=run_trace,
            task_graph=task_graph,
        )


_governance_service = GovernanceService(
    override_store=build_model_store(OverrideDecision, "decision_id", "override_decisions"),
    escalation_store=build_model_store(EscalationSummary, "escalation_id", "escalation_summaries"),
)


def get_governance_service() -> GovernanceService:
    return _governance_service
