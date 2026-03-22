from __future__ import annotations

from pydantic import BaseModel, Field

from app.company.models import BudgetScope, TriggerPolicy
from app.skills.models import SkillManifest


class PersonaPack(BaseModel):
    persona_id: str
    role_name: str
    division: str
    source_path: str
    source_url: str
    mission: str
    workflow_hints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    memory_instructions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EmployeeRoleContract(BaseModel):
    charter: list[str] = Field(default_factory=list)
    decision_lens: list[str] = Field(default_factory=list)
    preferred_deliverables: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    handoff_style: list[str] = Field(default_factory=list)
    escalation_triggers: list[str] = Field(default_factory=list)
    role_boundaries: list[str] = Field(default_factory=list)
    collaboration_rules: list[str] = Field(default_factory=list)
    negative_instructions: list[str] = Field(default_factory=list)


class AgentProfile(BaseModel):
    employee_id: str
    role: str
    department: str
    capabilities: list[str] = Field(default_factory=list)
    allowed_tool_classes: list[str] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)


class EmployeePackMemoryProfile(BaseModel):
    private_namespace: str
    department_namespace: str
    company_access_profile: str
    session_recall_rules: list[str] = Field(default_factory=list)
    remember_rules: list[str] = Field(default_factory=list)
    handoff_rules: list[str] = Field(default_factory=list)


class EmployeePack(BaseModel):
    employee_id: str
    employee_name: str
    department: str
    summary: str
    source_persona_packs: list[PersonaPack] = Field(default_factory=list)
    operating_modes: list[str] = Field(default_factory=list)
    recipe_eligibility: list[str] = Field(default_factory=list)
    budget_scope: BudgetScope
    heartbeat_policy: TriggerPolicy | None = None
    agent_profile: AgentProfile
    role_contract: EmployeeRoleContract
    memory_profile: EmployeePackMemoryProfile
    professional_skills: list[SkillManifest] = Field(default_factory=list)
    general_skills: list[SkillManifest] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
