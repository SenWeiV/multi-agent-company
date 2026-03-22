from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SkillSourceRef(BaseModel):
    repo_url: str
    repo_name: str
    commit_sha: str
    path: str
    license: str
    install_method: str
    verify_command: str
    local_path: str


class SkillManifest(BaseModel):
    skill_id: str
    skill_name: str
    summary: str
    scope: Literal["professional", "general"]
    role_owner: str | None = None
    source_ref: SkillSourceRef
    entrypoint_type: Literal["instructional_skill", "tool_backed_skill"] = "instructional_skill"
    invocation_contract: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    fit_rationale: str | None = None
    enabled: bool = True


class NativeSkillExportFile(BaseModel):
    path: str
    content: str


class NativeSkillExport(BaseModel):
    employee_id: str
    skill_id: str
    skill_name: str
    scope: Literal["professional", "general"]
    native_skill_name: str
    relative_dir: str
    skill_md_path: str
    skill_md_content: str
    files: list[NativeSkillExportFile] = Field(default_factory=list)
    source_ref: SkillSourceRef
    entrypoint_type: Literal["instructional_skill", "tool_backed_skill"] = "instructional_skill"
    fit_rationale: str | None = None


class EmployeeSkillPack(BaseModel):
    professional_skills: list[SkillManifest] = Field(default_factory=list)
    general_skills: list[SkillManifest] = Field(default_factory=list)


class SkillInvocationRequest(BaseModel):
    user_goal: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class SkillInvocationResult(BaseModel):
    employee_id: str
    skill_id: str
    skill_name: str
    scope: Literal["professional", "general"]
    entrypoint_type: Literal["instructional_skill", "tool_backed_skill"]
    source_ref: SkillSourceRef
    invocation_prompt: str
    source_excerpt: str
    status: Literal["ready", "failed"] = "ready"
    detail: str | None = None


class SkillInvocationRecord(BaseModel):
    invocation_id: str
    employee_id: str
    skill_id: str
    scope: Literal["professional", "general"]
    status: Literal["ready", "failed"]
    detail: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SkillValidationIssue(BaseModel):
    employee_id: str | None = None
    skill_id: str | None = None
    issue_type: str
    detail: str


class SkillCatalogValidationResult(BaseModel):
    ok: bool
    professional_skill_count_by_employee: dict[str, int] = Field(default_factory=dict)
    general_skill_count_by_employee: dict[str, int] = Field(default_factory=dict)
    issues: list[SkillValidationIssue] = Field(default_factory=list)
