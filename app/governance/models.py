from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from app.company.models import WorkTicket
from app.control_plane.models import Checkpoint, RunTrace, TaskGraph


class OverrideDecision(BaseModel):
    decision_id: str
    work_ticket_ref: str
    target: str = "current_path"
    new_direction: str
    rollback_ref: str
    supersede_refs: list[str] = Field(default_factory=list)
    notes: str
    created_by: str = "ceo"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EscalationSummary(BaseModel):
    escalation_id: str
    work_ticket_ref: str
    reason: str
    conflict_points: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    checkpoint_ref: str | None = None
    created_by: str = "chief-of-staff"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OverrideRecoveryRequest(BaseModel):
    work_ticket_id: str
    checkpoint_id: str | None = None
    new_direction: str
    summary: str
    target: str = "current_path"
    created_by: str = "ceo"


class EscalationRequest(BaseModel):
    work_ticket_id: str
    reason: str
    conflict_points: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None
    created_by: str = "chief-of-staff"


class OverrideRecoveryResult(BaseModel):
    override_decision: OverrideDecision
    checkpoint: Checkpoint
    work_ticket: WorkTicket
    run_trace: RunTrace
    task_graph: TaskGraph | None = None


class EscalationResult(BaseModel):
    escalation_summary: EscalationSummary
    checkpoint: Checkpoint | None = None
    work_ticket: WorkTicket
    run_trace: RunTrace
    task_graph: TaskGraph | None = None
