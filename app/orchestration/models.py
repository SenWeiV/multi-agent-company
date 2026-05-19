from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DiscussionRole(str, Enum):
    LEAD = "lead"
    PARTICIPANT = "participant"
    REVIEWER = "reviewer"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class PhaseParticipant(BaseModel):
    employee_id: str
    role: DiscussionRole


class DiscussionPhase(BaseModel):
    phase_id: str
    title: str
    lead_id: str
    participants: list[PhaseParticipant] = Field(default_factory=list)
    max_turns: int = 10
    status: PhaseStatus = PhaseStatus.PENDING
    turns_used: int = 0


class DiscussionPlan(BaseModel):
    phases: list[DiscussionPhase]
    current_phase_index: int = 0
    global_turns_used: int = 0


class PhaseTransitionSignal(BaseModel):
    phase_complete: bool = False
    next_speaker: str | None = None
    reason: str | None = None


class PhaseTurnRecord(BaseModel):
    speaker_id: str
    role: DiscussionRole
    reply_text: str
