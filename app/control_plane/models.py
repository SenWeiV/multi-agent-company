from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.company.models import BudgetScope, TriggerType, WorkTicket
from app.executive_office.models import CommandClassificationResult, InteractionMode


class TaskNodeStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"
    ACTIVE = "active"
    COMPLETED = "completed"


class TaskGraphStatus(StrEnum):
    READY = "ready"
    ACTIVE = "active"
    COMPLETED = "completed"
    ESCALATED = "escalated"


class RunTraceStatus(StrEnum):
    ROUTED = "routed"
    ACTIVE = "active"
    COMPLETED = "completed"
    ESCALATED = "escalated"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class BudgetDecisionStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"


class TriggerValidationStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CheckpointKind(StrEnum):
    FORMAL = "formal"
    LIGHTWEIGHT = "lightweight"


class TaskNode(BaseModel):
    node_id: str
    title: str
    owner_department: str
    status: TaskNodeStatus
    depends_on: list[str] = Field(default_factory=list)
    output_kind: str | None = None


class TaskGraph(BaseModel):
    taskgraph_id: str
    interaction_mode: InteractionMode
    workflow_recipe: str = "default"
    status: TaskGraphStatus
    goal_lineage_ref: str
    work_ticket_ref: str
    nodes: list[TaskNode] = Field(default_factory=list)


class RunEvent(BaseModel):
    event_type: str
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, str] = Field(default_factory=dict)


class RunTrace(BaseModel):
    runtrace_id: str
    interaction_mode: InteractionMode
    workflow_recipe: str = "default"
    trigger_type: TriggerType
    status: RunTraceStatus
    surface: str = "dashboard"
    thread_ref: str | None = None
    channel_ref: str | None = None
    goal_lineage_ref: str
    work_ticket_ref: str
    taskgraph_ref: str | None = None
    activated_departments: list[str] = Field(default_factory=list)
    visible_speakers: list[str] = Field(default_factory=list)
    dispatch_targets: list[str] = Field(default_factory=list)
    agent_turn_refs: list[str] = Field(default_factory=list)
    handoff_origin: str | None = None
    handoff_resolution_basis: str | None = None
    collaboration_intent: str | None = None
    reply_visible_named_targets: list[str] = Field(default_factory=list)
    handoff_contract_violation: bool = False
    handoff_repetition_violation: bool = False
    supersedes_runtrace_ref: str | None = None
    superseded_by_runtrace_ref: str | None = None
    visible_turn_count: int = 0
    delivery_guard_epoch: int = 0
    interruption_reason: str | None = None
    interruption_dispatch_targets: list[str] = Field(default_factory=list)
    spoken_bot_ids: list[str] = Field(default_factory=list)
    remaining_bot_ids: list[str] = Field(default_factory=list)
    remaining_turn_budget: int = 0
    stop_reason: str | None = None
    stopped_by_turn_limit: bool = False
    events: list[RunEvent] = Field(default_factory=list)


class BudgetCheck(BaseModel):
    scope: BudgetScope
    estimated_cost: float
    limit: float | None = None
    warning_threshold: float
    status: BudgetDecisionStatus
    requires_approval: bool
    override_rule: str
    message: str


class TriggerContext(BaseModel):
    trigger_type: TriggerType
    status: TriggerValidationStatus
    routing_rule: str
    recurring_work: str | None = None
    message: str


class Checkpoint(BaseModel):
    checkpoint_id: str
    work_ticket_ref: str
    taskgraph_ref: str | None = None
    runtrace_ref: str
    goal_lineage_ref: str
    kind: CheckpointKind
    stage: str
    task_graph_snapshot: TaskGraph | None = None
    memory_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[str] = Field(default_factory=list)
    approval_state: str = "pending"
    verdict_state: str = "pending"
    rollback_scope: str = "task_graph"
    superseded_by: str | None = None


class CommandIntakeResult(BaseModel):
    classification: CommandClassificationResult
    work_ticket: WorkTicket
    task_graph: TaskGraph | None = None
    run_trace: RunTrace
    budget_checks: list[BudgetCheck] = Field(default_factory=list)
    trigger_context: TriggerContext
    checkpoint: Checkpoint | None = None
