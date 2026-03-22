from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ArtifactBlobRecord(BaseModel):
    object_id: str
    bucket: str
    object_key: str
    filename: str
    content_type: str
    source_type: str
    source_ref: str
    summary: str
    work_ticket_ref: str | None = None
    thread_ref: str | None = None
    runtrace_ref: str | None = None
    size_bytes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ArtifactBlobContent(BaseModel):
    record: ArtifactBlobRecord
    content: str
