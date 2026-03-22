from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict

from pydantic import BaseModel, Field

from app.company.models import WorkTicket
from app.control_plane.models import RunTrace, TaskGraph
from app.conversation.models import ConversationThread
from app.memory.models import MemoryRecord


class PostLaunchFollowUpLink(BaseModel):
    source_work_ticket_ref: str
    source_title: str
    source_runtrace_ref: str
    follow_up_ticket_ref: str
    follow_up_title: str
    follow_up_runtrace_ref: str | None = None
    follow_up_thread_ref: str | None = None
    trigger_type: str = "scheduled_heartbeat"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "created"
    note: str = ""


class PostLaunchRoutingResult(BaseModel):
    already_exists: bool = False
    link: PostLaunchFollowUpLink
    follow_up_work_ticket: WorkTicket
    follow_up_run_trace: RunTrace
    follow_up_task_graph: TaskGraph | None = None
    follow_up_thread: ConversationThread | None = None


class PostLaunchSummary(BaseModel):
    launch_tickets: list[WorkTicket] = Field(default_factory=list)
    follow_ups: list[PostLaunchFollowUpLink] = Field(default_factory=list)
    feedback_memories: list[MemoryRecord] = Field(default_factory=list)


class RuntimeExecutionResult(BaseModel):
    runtime_thread_id: str
    work_ticket: WorkTicket
    task_graph: TaskGraph
    run_trace: RunTrace
    conversation_thread: ConversationThread | None = None
    executed_nodes: list[str] = Field(default_factory=list)
    node_outputs: dict[str, str] = Field(default_factory=dict)
    memory_records: list[MemoryRecord] = Field(default_factory=list)
    post_launch_follow_up: PostLaunchRoutingResult | None = None


class RuntimeState(TypedDict, total=False):
    work_ticket_id: str
    work_ticket_title: str
    work_ticket_type: str
    taskgraph_id: str
    runtrace_id: str
    surface: str
    channel_ref: str
    executed_nodes: list[str]
    node_outputs: dict[str, str]
