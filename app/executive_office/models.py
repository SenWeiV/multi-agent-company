from enum import StrEnum

from pydantic import BaseModel, Field

from app.company.models import GoalLineage, TriggerType, WorkTicket


class InteractionMode(StrEnum):
    IDEA_CAPTURE = "idea_capture"
    QUICK_CONSULT = "quick_consult"
    DEPARTMENT_TASK = "department_task"
    FORMAL_PROJECT = "formal_project"
    REVIEW_DECISION = "review_decision"
    OVERRIDE_RECOVERY = "override_recovery"
    ESCALATION = "escalation"


class ParticipationScope(StrEnum):
    EXECUTIVE_ONLY = "executive_only"
    SINGLE_DEPARTMENT = "single_department"
    MULTI_DEPARTMENT = "multi_department"
    FULL_PROJECT_CHAIN = "full_project_chain"


class CEOCommand(BaseModel):
    intent: str
    priority: str = "normal"
    time_horizon: str = "near_term"
    delegation_mode: str = "default"
    expected_outcome: str | None = None
    interaction_mode: InteractionMode | None = None
    activation_hint: list[str] = Field(default_factory=list)
    trigger_type: TriggerType = TriggerType.MANUAL
    budget_estimate: float | None = None
    budget_override_requested: bool = False
    checkpoint_requested: bool = False
    surface: str = "dashboard"
    thread_ref: str | None = None
    entry_channel: str | None = None


class GoalRequest(BaseModel):
    goal: str
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    risk_level: str = "normal"
    approval_policy: str = "default"
    interaction_mode: InteractionMode
    participation_scope: ParticipationScope
    goal_lineage_ref: str
    workflow_recipe: str = "default"


class CommandClassificationResult(BaseModel):
    interaction_mode: InteractionMode
    participation_scope: ParticipationScope
    trigger_type: TriggerType
    workflow_recipe: str = "default"
    recommended_departments: list[str]
    goal_request: GoalRequest
    goal_lineage: GoalLineage
    work_ticket: WorkTicket
