from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.control_plane.models import CommandIntakeResult
from app.executive_office.models import CEOCommand, InteractionMode


class ConversationSurface(StrEnum):
    DASHBOARD = "dashboard"
    FEISHU_DM = "feishu_dm"
    FEISHU_GROUP = "feishu_group"


class SpeakerMode(StrEnum):
    DIRECT = "direct"
    CHIEF_OF_STAFF_MODERATED = "chief_of_staff_moderated"
    MENTION_FAN_OUT_VISIBLE = "mention_fan_out_visible"


class PendingHandoffState(BaseModel):
    source_agent_id: str
    target_agent_id: str
    instruction: str | None = None
    reason: str | None = None
    source_runtrace_ref: str | None = None
    status: str = "active"


class ConversationThread(BaseModel):
    thread_id: str
    surface: ConversationSurface
    channel_id: str
    provider: str
    title: str
    participant_ids: list[str] = Field(default_factory=list)
    bound_agent_ids: list[str] = Field(default_factory=list)
    channel_binding_ref: str | None = None
    room_policy_ref: str | None = None
    interaction_mode: InteractionMode | None = None
    work_ticket_ref: str | None = None
    taskgraph_ref: str | None = None
    runtrace_ref: str | None = None
    active_runtrace_ref: str | None = None
    openclaw_session_refs: dict[str, str] = Field(default_factory=dict)
    visible_room_ref: str | None = None
    delivery_guard_epoch: int = 0
    last_committed_state: dict[str, Any] = Field(default_factory=dict)
    pending_handoff: PendingHandoffState | None = None
    superseded_runtrace_refs: list[str] = Field(default_factory=list)
    status: str = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BotSeatBinding(BaseModel):
    binding_id: str
    department: str
    virtual_employee: str
    feishu_app_id: str
    feishu_bot_identity: str
    binding_scope: str = "department"


class ChannelBinding(BaseModel):
    binding_id: str
    surface: ConversationSurface
    provider: str
    default_route: str
    mention_policy: str
    sync_back_policy: str
    room_policy_ref: str | None = None


class RoomPolicy(BaseModel):
    room_policy_id: str
    room_type: str
    speaker_mode: SpeakerMode
    visible_participants: list[str] = Field(default_factory=list)
    turn_taking_rule: str
    escalation_rule: str


class ConversationIntakeRequest(BaseModel):
    command: CEOCommand
    surface: ConversationSurface = ConversationSurface.DASHBOARD
    channel_id: str
    initiator_id: str = "ceo"
    participant_ids: list[str] = Field(default_factory=list)
    bound_agent_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    thread_id: str | None = None


class ConversationIntakeResult(BaseModel):
    thread: ConversationThread
    command_result: CommandIntakeResult


class ChannelBindingUpdateRequest(BaseModel):
    default_route: str
    mention_policy: str
    sync_back_policy: str
    room_policy_ref: str | None = None


class RoomPolicyUpdateRequest(BaseModel):
    speaker_mode: SpeakerMode
    visible_participants: list[str] = Field(default_factory=list)
    turn_taking_rule: str
    escalation_rule: str
