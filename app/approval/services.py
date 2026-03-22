from __future__ import annotations

import json
from uuid import uuid4

from app.approval.models import (
    ApprovalGate,
    ApprovalStatus,
    DecisionRecord,
    ReviewDecisionRequest,
    ReviewDecisionResult,
)
from app.control_plane.models import RunEvent, RunTraceStatus
from app.control_plane.services import get_control_plane_service
from app.memory.services import get_memory_service
from app.store import ModelStore, build_model_store


class ApprovalService:
    def __init__(
        self,
        approvals_store: ModelStore[ApprovalGate],
        decisions_store: ModelStore[DecisionRecord],
    ) -> None:
        self._approvals = approvals_store
        self._decisions = decisions_store

    def review_decision(self, request: ReviewDecisionRequest) -> ReviewDecisionResult:
        control_plane = get_control_plane_service()
        work_ticket = control_plane.get_required_work_ticket(request.work_ticket_id)
        run_trace = control_plane.get_required_run_trace(work_ticket.runtrace_ref or "")
        checkpoint = (
            control_plane.get_checkpoint(request.checkpoint_id)
            if request.checkpoint_id
            else control_plane.get_latest_checkpoint_for_ticket(work_ticket.ticket_id)
        )

        evidence_refs = request.evidence_refs or work_ticket.artifacts
        if not evidence_refs:
            raise ValueError("review_decision requires existing evidence refs")

        approval = ApprovalGate(
            approval_id=f"ap-{uuid4().hex[:8]}",
            work_ticket_ref=work_ticket.ticket_id,
            status=request.decision,
            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
            evidence_refs=evidence_refs,
            approver=request.approver,
            notes=request.summary,
        )
        approval = self._approvals.save(approval)

        decision = DecisionRecord(
            decision_id=f"dr-{uuid4().hex[:8]}",
            work_ticket_ref=work_ticket.ticket_id,
            verdict=request.decision,
            rationale=request.summary,
            evidence_refs=evidence_refs,
            checkpoint_ref=approval.checkpoint_ref,
            created_by=request.approver,
        )
        decision = self._decisions.save(decision)

        if checkpoint is not None:
            checkpoint = control_plane.update_checkpoint_approval(checkpoint.checkpoint_id, request.decision.value)

        if request.decision == ApprovalStatus.APPROVED:
            work_ticket = control_plane.set_work_ticket_status(work_ticket.ticket_id, "approved")
            run_trace = control_plane.append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="review_decision_recorded",
                    message="CEO review approved the current work ticket.",
                    metadata={"approval_id": approval.approval_id, "decision_id": decision.decision_id},
                ),
                status=RunTraceStatus.ACTIVE,
            )
        else:
            work_ticket = control_plane.set_work_ticket_status(work_ticket.ticket_id, "rejected")
            run_trace = control_plane.append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="review_decision_recorded",
                    message="CEO review rejected the current work ticket.",
                    metadata={"approval_id": approval.approval_id, "decision_id": decision.decision_id},
                ),
                status=RunTraceStatus.ESCALATED,
            )

        memory_records = get_memory_service().create_review_memories(
            work_ticket=work_ticket,
            run_trace=run_trace,
            checkpoint=checkpoint,
            verdict=request.decision.value,
            summary=request.summary,
            evidence_refs=evidence_refs,
        )
        if checkpoint is not None:
            for memory_record in memory_records:
                checkpoint = control_plane.attach_memory_to_checkpoint(checkpoint.checkpoint_id, memory_record.memory_id)

        return ReviewDecisionResult(
            approval_gate=approval,
            decision_record=decision,
            checkpoint=checkpoint,
            work_ticket=work_ticket,
            run_trace=run_trace,
        )

    def review_decision_from_feishu_card(self, payload: dict) -> ReviewDecisionResult:
        return self.review_decision(self._review_request_from_feishu_card(payload))

    def _review_request_from_feishu_card(self, payload: dict) -> ReviewDecisionRequest:
        action = payload.get("action") or {}
        raw_value = action.get("value") or action.get("form_value") or payload.get("value") or {}
        if isinstance(raw_value, str):
            raw_value = json.loads(raw_value)
        if not isinstance(raw_value, dict):
            raise ValueError("Invalid Feishu card callback payload: missing action.value")

        decision_raw = (raw_value.get("decision") or raw_value.get("verdict") or "").strip().lower()
        if not decision_raw:
            raise ValueError("Feishu card callback missing decision")

        try:
            decision = ApprovalStatus(decision_raw)
        except ValueError as exc:
            raise ValueError(f"Unsupported Feishu card decision: {decision_raw}") from exc

        work_ticket_id = raw_value.get("work_ticket_id") or raw_value.get("ticket_id")
        if not work_ticket_id:
            raise ValueError("Feishu card callback missing work_ticket_id")

        operator = payload.get("operator") or {}
        operator_id = (
            ((operator.get("operator_id") or {}).get("open_id"))
            or ((operator.get("operator_id") or {}).get("user_id"))
            or operator.get("name")
            or "feishu_card"
        )
        summary = (
            raw_value.get("summary")
            or raw_value.get("notes")
            or f"Feishu card review decision: {decision.value}"
        )
        evidence_refs = raw_value.get("evidence_refs") or []
        if not isinstance(evidence_refs, list):
            evidence_refs = [str(evidence_refs)]

        return ReviewDecisionRequest(
            work_ticket_id=work_ticket_id,
            decision=decision,
            summary=summary,
            checkpoint_id=raw_value.get("checkpoint_id"),
            approver=str(raw_value.get("approver") or operator_id or "feishu_card"),
            evidence_refs=[str(item) for item in evidence_refs if str(item).strip()],
        )

    def list_approvals_for_ticket(self, ticket_id: str) -> list[ApprovalGate]:
        return [approval for approval in self._approvals.list() if approval.work_ticket_ref == ticket_id]


_approval_service = ApprovalService(
    approvals_store=build_model_store(ApprovalGate, "approval_id", "approval_gates"),
    decisions_store=build_model_store(DecisionRecord, "decision_id", "approval_decision_records"),
)


def get_approval_service() -> ApprovalService:
    return _approval_service
