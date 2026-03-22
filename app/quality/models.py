from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.company.models import WorkTicket
from app.control_plane.models import Checkpoint, RunTrace, TaskGraph


class QualityVerdict(StrEnum):
    GO = "go"
    NO_GO = "no_go"


class EvidenceArtifact(BaseModel):
    artifact_id: str
    work_ticket_ref: str
    taskgraph_ref: str | None = None
    runtrace_ref: str
    checkpoint_ref: str | None = None
    artifact_type: str = "quality_evidence"
    summary: str
    evidence_points: list[str] = Field(default_factory=list)
    object_ref: str | None = None
    object_bucket: str | None = None
    object_key: str | None = None
    created_by: str = "quality-lead"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QualityDecisionRecord(BaseModel):
    decision_id: str
    work_ticket_ref: str
    decision_type: str = "quality_verdict"
    verdict: QualityVerdict
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    checkpoint_ref: str | None = None
    created_by: str = "quality-lead"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class QualityEvaluationRequest(BaseModel):
    work_ticket_id: str
    verdict: QualityVerdict
    summary: str
    evidence_points: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None
    created_by: str = "quality-lead"


class QualityEvaluationResult(BaseModel):
    evidence_artifact: EvidenceArtifact
    decision_record: QualityDecisionRecord
    checkpoint: Checkpoint | None = None
    work_ticket: WorkTicket
    run_trace: RunTrace
    task_graph: TaskGraph | None = None
