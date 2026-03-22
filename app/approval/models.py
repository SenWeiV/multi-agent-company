from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.company.models import WorkTicket
from app.control_plane.models import Checkpoint, RunTrace


class ApprovalStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalGate(BaseModel):
    approval_id: str
    work_ticket_ref: str
    requested_action: str = "review_decision"
    status: ApprovalStatus
    checkpoint_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    approver: str = "ceo"
    notes: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DecisionRecord(BaseModel):
    decision_id: str
    work_ticket_ref: str
    decision_type: str = "review_decision"
    verdict: ApprovalStatus
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    checkpoint_ref: str | None = None
    created_by: str = "ceo"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReviewDecisionRequest(BaseModel):
    work_ticket_id: str
    decision: ApprovalStatus
    summary: str
    checkpoint_id: str | None = None
    approver: str = "ceo"
    evidence_refs: list[str] = Field(default_factory=list)


class ReviewDecisionResult(BaseModel):
    approval_gate: ApprovalGate
    decision_record: DecisionRecord
    checkpoint: Checkpoint | None = None
    work_ticket: WorkTicket
    run_trace: RunTrace


class FeishuCardReviewDecisionCallback(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
