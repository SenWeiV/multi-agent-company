from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.conversation.models import ConversationSurface


class FeishuBotAppConfig(BaseModel):
    employee_id: str
    app_id: str
    app_secret: str
    verification_token: str | None = None
    encrypt_key: str | None = None
    bot_identity: str | None = None
    bot_open_id: str | None = None
    display_name: str | None = None


class FeishuInboundEventRecord(BaseModel):
    record_id: str
    message_id: str
    event_id: str | None = None
    app_id: str
    surface: ConversationSurface
    chat_id: str
    thread_ref: str | None = None
    work_ticket_ref: str | None = None
    runtrace_ref: str | None = None
    sender_id: str | None = None
    text: str | None = None
    dispatch_mode: str | None = None
    dispatch_targets: list[str] = Field(default_factory=list)
    dispatch_resolution_basis: str | None = None
    collaboration_intent: str | None = None
    target_agent_ids: list[str] = Field(default_factory=list)
    deterministic_name_target_ids: list[str] = Field(default_factory=list)
    semantic_dispatch_target_ids: list[str] = Field(default_factory=list)
    deterministic_text_target_ids: list[str] = Field(default_factory=list)
    semantic_handoff_target_ids: list[str] = Field(default_factory=list)
    forced_handoff_targets: list[str] = Field(default_factory=list)
    supersedes_runtrace_ref: str | None = None
    active_thread_runtrace_ref: str | None = None
    interruption_dispatch_targets: list[str] = Field(default_factory=list)
    delivery_guard_epoch: int | None = None
    raw_mentions_summary: list[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="before")
    @classmethod
    def default_record_id(cls, data: object) -> object:
        if isinstance(data, dict) and "record_id" not in data and "message_id" in data:
            data = {**data, "record_id": data["message_id"]}
        return data


class FeishuWebhookResult(BaseModel):
    status: Literal["challenge", "processed", "duplicate", "ignored"]
    app_id: str | None = None
    surface: ConversationSurface | None = None
    message_id: str | None = None
    thread_id: str | None = None
    work_ticket_id: str | None = None
    runtrace_id: str | None = None
    challenge: str | None = None
    reply_sent: bool = False
    reply_count: int = 0
    target_agent_ids: list[str] = Field(default_factory=list)
    dispatch_mode: str | None = None
    detail: str | None = None


class FeishuGroupDebugEventRecord(BaseModel):
    debug_event_id: str
    message_id: str
    event_id: str | None = None
    app_id: str
    surface: ConversationSurface
    chat_id: str
    sender_id: str | None = None
    text: str | None = None
    raw_message_content: str | None = None
    raw_mentions: list[dict[str, Any]] = Field(default_factory=list)
    raw_mentions_summary: list[str] = Field(default_factory=list)
    dispatch_mode: str | None = None
    dispatch_targets: list[str] = Field(default_factory=list)
    dispatch_resolution_basis: str | None = None
    collaboration_intent: str | None = None
    target_agent_ids: list[str] = Field(default_factory=list)
    deterministic_name_target_ids: list[str] = Field(default_factory=list)
    semantic_dispatch_target_ids: list[str] = Field(default_factory=list)
    deterministic_text_target_ids: list[str] = Field(default_factory=list)
    semantic_handoff_target_ids: list[str] = Field(default_factory=list)
    semantic_handoff_candidates: list[dict[str, Any]] = Field(default_factory=list)
    matched_employee_id: str | None = None
    match_basis: str | None = None
    target_resolution_basis: str | None = None
    processed_status: str = "processed"
    detail: str | None = None
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FeishuMentionDispatchResult(BaseModel):
    app_id: str
    chat_id: str
    message_id: str
    target_agent_ids: list[str] = Field(default_factory=list)
    dispatch_mode: str = "single_agent"


class FeishuSendMessageRequest(BaseModel):
    app_id: str
    chat_id: str
    text: str
    mention_employee_ids: list[str] = Field(default_factory=list)
    receive_id_type: str = "chat_id"
    work_ticket_ref: str | None = None
    thread_ref: str | None = None
    runtrace_ref: str | None = None
    delivery_guard_epoch: int | None = None
    source_kind: str = "manual"
    idempotency_key: str | None = None


class FeishuSendMessageResult(BaseModel):
    app_id: str
    receive_id_type: str
    receive_id: str
    message_id: str | None = None
    status: str = "sent"
    attempt_count: int = 1
    mention_employee_ids: list[str] = Field(default_factory=list)
    outbound_ref: str | None = None
    attachment_object_ref: str | None = None
    error_detail: str | None = None


class FeishuReplayMessageResult(BaseModel):
    source_outbound_ref: str
    replay_attempt_count: int
    replay_result: FeishuSendMessageResult


class FeishuReplayAuditEntryView(BaseModel):
    outbound_id: str
    app_id: str
    receive_id: str
    source_kind: str
    status: str
    attempt_count: int
    created_at: datetime
    error_detail: str | None = None
    replay_source_outbound_ref: str | None = None
    replay_root_outbound_ref: str | None = None
    work_ticket_ref: str | None = None
    thread_ref: str | None = None
    runtrace_ref: str | None = None


class FeishuDeadLetterDetailView(BaseModel):
    dead_letter: FeishuOutboundMessageRecord
    replay_history: list[FeishuReplayAuditEntryView] = Field(default_factory=list)


class FeishuOutboundMessageRecord(BaseModel):
    outbound_id: str
    app_id: str
    receive_id_type: str
    receive_id: str
    message_id: str | None = None
    text: str
    mention_employee_ids: list[str] = Field(default_factory=list)
    work_ticket_ref: str | None = None
    thread_ref: str | None = None
    runtrace_ref: str | None = None
    source_kind: str = "manual"
    idempotency_key: str | None = None
    status: str = "sent"
    attempt_count: int = 1
    delivery_guard_epoch: int | None = None
    delivery_guard_checked_at: datetime | None = None
    stale_drop_reason: str | None = None
    dropped_as_stale: bool = False
    error_detail: str | None = None
    replay_attempt_count: int = 0
    replayed_by_outbound_ref: str | None = None
    replay_source_outbound_ref: str | None = None
    replay_root_outbound_ref: str | None = None
    last_replay_at: datetime | None = None
    attachment_object_ref: str | None = None
    attachment_bucket: str | None = None
    attachment_object_key: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_attempt_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FeishuBotAppView(BaseModel):
    employee_id: str
    app_id: str
    bot_identity: str | None = None
    bot_open_id: str | None = None
    display_name: str | None = None
