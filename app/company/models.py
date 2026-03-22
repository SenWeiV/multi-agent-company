from enum import StrEnum

from pydantic import BaseModel, Field


class ActivationLevel(StrEnum):
    ALWAYS_ON = "always_on"
    ON_DEMAND = "on_demand"
    SITUATIONAL_EXPANSION = "situational_expansion"


class BudgetScope(StrEnum):
    COMPANY = "company"
    DEPARTMENT = "department"
    EMPLOYEE = "employee"
    TASK = "task"


class TriggerType(StrEnum):
    MANUAL = "manual"
    EVENT_BASED = "event_based"
    SCHEDULED_HEARTBEAT = "scheduled_heartbeat"


class BudgetPolicy(BaseModel):
    scope: BudgetScope
    limit: float | None = None
    warning_threshold: float = Field(default=0.8, ge=0, le=1)
    hard_stop: bool = True
    override_rule: str


class TriggerPolicy(BaseModel):
    trigger_type: TriggerType
    schedule: str | None = None
    event_source: str | None = None
    routing_rule: str


class CompanyProfile(BaseModel):
    company_id: str
    company_name: str
    company_type: str
    stage: str
    strategic_focus: list[str]
    default_departments: list[str]
    activation_policy: dict[str, list[str]]
    budget_policy: list[BudgetPolicy]
    trigger_defaults: list[TriggerPolicy]


class VirtualDepartment(BaseModel):
    department_name: str
    charter: str
    activation_level: ActivationLevel
    default_employee: str
    upstream_sources: list[str]
    budget_scope: BudgetScope
    heartbeat_policy: TriggerPolicy | None = None


class VirtualEmployee(BaseModel):
    employee_id: str
    department: str
    employee_name: str
    source_persona_packs: list[str]
    operating_modes: list[str]
    kpis: list[str]
    budget_scope: BudgetScope
    heartbeat_policy: TriggerPolicy | None = None


class DepartmentSeatMapEntry(BaseModel):
    department: str
    employee: str
    source_persona_packs: list[str]
    recipe_eligibility: list[str]
    private_namespace: str
    department_namespace: str
    company_access_profile: str


class GoalLineage(BaseModel):
    goal_lineage_id: str
    company_goal: str
    initiative: str
    project_goal: str
    task_goal: str
    execution_ref: str


class WorkTicket(BaseModel):
    ticket_id: str
    title: str
    ticket_type: str
    thread_ref: str | None = None
    channel_ref: str | None = None
    taskgraph_ref: str | None = None
    runtrace_ref: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    supersede_refs: list[str] = Field(default_factory=list)
    status: str = "draft"
