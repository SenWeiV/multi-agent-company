from __future__ import annotations

from uuid import uuid4

from app.artifacts.services import get_artifact_store_service
from app.control_plane.models import RunEvent, RunTraceStatus, TaskGraphStatus
from app.control_plane.services import get_control_plane_service
from app.memory.services import get_memory_service
from app.quality.models import (
    EvidenceArtifact,
    QualityDecisionRecord,
    QualityEvaluationRequest,
    QualityEvaluationResult,
    QualityVerdict,
)
from app.store import ModelStore, build_model_store


class QualityService:
    def __init__(
        self,
        artifacts_store: ModelStore[EvidenceArtifact],
        decisions_store: ModelStore[QualityDecisionRecord],
    ) -> None:
        self._artifacts = artifacts_store
        self._decisions = decisions_store

    def evaluate(self, request: QualityEvaluationRequest) -> QualityEvaluationResult:
        control_plane = get_control_plane_service()
        work_ticket = control_plane.get_required_work_ticket(request.work_ticket_id)
        run_trace = control_plane.get_required_run_trace(work_ticket.runtrace_ref or "")
        checkpoint = (
            control_plane.get_checkpoint(request.checkpoint_id)
            if request.checkpoint_id
            else control_plane.get_latest_checkpoint_for_ticket(work_ticket.ticket_id)
        )
        task_graph = control_plane.get_task_graph(work_ticket.taskgraph_ref) if work_ticket.taskgraph_ref else None

        artifact = EvidenceArtifact(
            artifact_id=f"ea-{uuid4().hex[:8]}",
            work_ticket_ref=work_ticket.ticket_id,
            taskgraph_ref=work_ticket.taskgraph_ref,
            runtrace_ref=run_trace.runtrace_id,
            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
            summary=request.summary,
            evidence_points=request.evidence_points,
            created_by=request.created_by,
        )
        artifact_blob = get_artifact_store_service().store_json(
            source_type="quality_evidence",
            source_ref=artifact.artifact_id,
            payload={
                "artifact": artifact.model_dump(mode="json"),
                "evaluation_request": request.model_dump(mode="json"),
            },
            filename="evidence.json",
            summary=request.summary,
            work_ticket_ref=work_ticket.ticket_id,
            runtrace_ref=run_trace.runtrace_id,
        )
        artifact = artifact.model_copy(
            update={
                "object_ref": artifact_blob.object_id,
                "object_bucket": artifact_blob.bucket,
                "object_key": artifact_blob.object_key,
            }
        )
        artifact = self._artifacts.save(artifact)
        work_ticket = control_plane.attach_artifact_to_ticket(work_ticket.ticket_id, artifact.artifact_id)
        if checkpoint is not None:
            checkpoint = control_plane.attach_artifact_to_checkpoint(checkpoint.checkpoint_id, artifact.artifact_id)

        decision = QualityDecisionRecord(
            decision_id=f"qd-{uuid4().hex[:8]}",
            work_ticket_ref=work_ticket.ticket_id,
            verdict=request.verdict,
            rationale=request.summary,
            evidence_refs=[artifact.artifact_id],
            checkpoint_ref=artifact.checkpoint_ref,
            created_by=request.created_by,
        )
        decision = self._decisions.save(decision)

        if checkpoint is not None:
            checkpoint = control_plane.update_checkpoint_verdict(checkpoint.checkpoint_id, request.verdict.value)

        if request.verdict == QualityVerdict.NO_GO:
            work_ticket = control_plane.set_work_ticket_status(work_ticket.ticket_id, "quality_no_go")
            if task_graph is not None:
                task_graph = control_plane.set_task_graph_status(task_graph.taskgraph_id, TaskGraphStatus.ESCALATED)
            run_trace = control_plane.append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="quality_verdict_recorded",
                    message="Quality verdict recorded as NO-GO.",
                    metadata={"artifact_id": artifact.artifact_id, "decision_id": decision.decision_id},
                ),
                status=RunTraceStatus.ESCALATED,
            )
        else:
            work_ticket = control_plane.set_work_ticket_status(work_ticket.ticket_id, "quality_go")
            if task_graph is not None:
                task_graph = control_plane.set_task_graph_status(task_graph.taskgraph_id, TaskGraphStatus.ACTIVE)
            run_trace = control_plane.append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="quality_verdict_recorded",
                    message="Quality verdict recorded as GO.",
                    metadata={"artifact_id": artifact.artifact_id, "decision_id": decision.decision_id},
                ),
                status=RunTraceStatus.ACTIVE,
            )

        memory_records = get_memory_service().create_quality_memories(
            work_ticket=work_ticket,
            run_trace=run_trace,
            checkpoint=checkpoint,
            verdict=request.verdict.value,
            summary=request.summary,
            artifact_refs=[artifact.artifact_id],
        )
        if checkpoint is not None:
            for memory_record in memory_records:
                checkpoint = control_plane.attach_memory_to_checkpoint(checkpoint.checkpoint_id, memory_record.memory_id)

        return QualityEvaluationResult(
            evidence_artifact=artifact,
            decision_record=decision,
            checkpoint=checkpoint,
            work_ticket=work_ticket,
            run_trace=run_trace,
            task_graph=task_graph,
        )

    def list_artifacts_for_ticket(self, ticket_id: str) -> list[EvidenceArtifact]:
        return [artifact for artifact in self._artifacts.list() if artifact.work_ticket_ref == ticket_id]


_quality_service = QualityService(
    artifacts_store=build_model_store(EvidenceArtifact, "artifact_id", "quality_evidence_artifacts"),
    decisions_store=build_model_store(QualityDecisionRecord, "decision_id", "quality_decision_records"),
)


def get_quality_service() -> QualityService:
    return _quality_service
