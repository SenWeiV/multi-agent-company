from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MemoryScope(StrEnum):
    RUN = "run"
    AGENT_PRIVATE = "agent_private"
    DEPARTMENT_SHARED = "department_shared"
    COMPANY_SHARED = "company_shared"


class MemoryKind(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    EVIDENCE = "evidence"


class MemoryNamespace(BaseModel):
    namespace_id: str
    scope: MemoryScope
    owner: str
    read_policy: str
    write_policy: str
    promotion_policy: str


class MemoryRecord(BaseModel):
    memory_id: str
    namespace_id: str
    scope: MemoryScope
    scope_id: str
    owner_id: str
    kind: MemoryKind
    visibility: str
    content: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.8
    promotion_state: str = "draft"
    version: int = 1
    checkpoint_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    retention: str = "default"
    source_trace: str | None = None
    work_ticket_ref: str | None = None
    thread_ref: str | None = None
    superseded_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RecallQuery(BaseModel):
    scope_filter: list[MemoryScope] = Field(default_factory=list)
    kind_filter: list[MemoryKind] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    project: str | None = None
    department: str | None = None
    receiver: str | None = None
    time_window: str | None = None
    min_confidence: float = 0.0
    requester_id: str = "ceo"
    requester_department: str | None = None


class MemoryWriteRequest(BaseModel):
    namespace_id: str
    owner_id: str
    kind: MemoryKind
    content: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.8
    promotion_state: str = "draft"
    checkpoint_ref: str | None = None
    artifact_refs: list[str] = Field(default_factory=list)
    retention: str = "default"
    source_trace: str | None = None
    work_ticket_ref: str | None = None
    thread_ref: str | None = None
