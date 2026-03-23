from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from app.skills.models import SkillManifest
from app.memory.models import MemoryNamespace, MemoryRecord
from app.skills.models import SkillSourceRef


class OpenClawModelCost(BaseModel):
    input: float = 0.0
    output: float = 0.0
    cacheRead: float = 0.0
    cacheWrite: float = 0.0


class OpenClawModelCompat(BaseModel):
    thinkingFormat: str | None = None


class OpenClawProviderModel(BaseModel):
    id: str
    name: str
    reasoning: bool = False
    input: list[str] = Field(default_factory=list)
    cost: OpenClawModelCost = Field(default_factory=OpenClawModelCost)
    contextWindow: int = 0
    maxTokens: int = 0
    compat: OpenClawModelCompat = Field(default_factory=OpenClawModelCompat)


class OpenClawProviderConfig(BaseModel):
    baseUrl: str
    apiKey: str
    api: str
    models: list[OpenClawProviderModel] = Field(default_factory=list)


class OpenClawAgentModelDefaults(BaseModel):
    primary: str


class OpenClawAgentDefaults(BaseModel):
    model: OpenClawAgentModelDefaults
    models: dict[str, dict] = Field(default_factory=dict)


class OpenClawGatewayConfig(BaseModel):
    mode: str = "local"


class OpenClawModelRegistry(BaseModel):
    mode: str = "merge"
    providers: dict[str, OpenClawProviderConfig] = Field(default_factory=dict)


class OpenClawRuntimeConfig(BaseModel):
    models: OpenClawModelRegistry
    agents: dict[str, OpenClawAgentDefaults] = Field(default_factory=dict)
    gateway: OpenClawGatewayConfig = Field(default_factory=OpenClawGatewayConfig)


class OpenClawIdentityProfile(BaseModel):
    identity: str
    soul: list[str] = Field(default_factory=list)
    reply_style: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)
    role_charter: list[str] = Field(default_factory=list)
    decision_lens: list[str] = Field(default_factory=list)
    preferred_deliverables: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    handoff_style: list[str] = Field(default_factory=list)
    escalation_triggers: list[str] = Field(default_factory=list)
    role_boundaries: list[str] = Field(default_factory=list)
    collaboration_rules: list[str] = Field(default_factory=list)
    negative_instructions: list[str] = Field(default_factory=list)


class OpenClawWorkspaceFile(BaseModel):
    path: str
    content: str


class OpenClawWorkspaceBundle(BaseModel):
    employee_id: str
    openclaw_agent_id: str
    workspace_path: str
    agent_dir: str
    bootstrap_entrypoint: str = "BOOTSTRAP.md"
    bootstrap_files: list[OpenClawWorkspaceFile] = Field(default_factory=list)
    tool_profile: str
    sandbox_profile: str
    channel_accounts: dict[str, str] = Field(default_factory=dict)
    professional_skills: list[SkillManifest] = Field(default_factory=list)
    general_skills: list[SkillManifest] = Field(default_factory=list)


class OpenClawWorkspaceFileOverride(BaseModel):
    override_id: str
    employee_id: str
    path: str
    content: str


class OpenClawAgentBinding(BaseModel):
    employee_id: str
    openclaw_agent_id: str
    workspace_home_ref: str
    workspace_path: str
    agent_dir: str
    primary_model_ref: str
    tool_profile: str
    sandbox_profile: str
    channel_accounts: dict[str, str] = Field(default_factory=dict)


class OpenClawSessionBinding(BaseModel):
    employee_id: str
    openclaw_agent_id: str
    surface: str
    channel_id: str
    session_key: str


class OpenClawAgentBindingOverride(BaseModel):
    employee_id: str
    tool_profile: str | None = None
    sandbox_profile: str | None = None


class OpenClawAgentBindingUpdateRequest(BaseModel):
    tool_profile: str
    sandbox_profile: str


class OpenClawHookOverride(BaseModel):
    hook_id: str
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)


class OpenClawHookUpdateRequest(BaseModel):
    enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)


class OpenClawAgentWorkspaceFileUpdateRequest(BaseModel):
    content: str


class OpenClawAgentConfig(BaseModel):
    employee_id: str
    employee_name: str
    department: str
    openclaw_agent_id: str
    primary_model_ref: str
    provider_name: str
    provider_base_url: str
    model_id: str
    model_name: str
    reasoning: bool = False
    context_window: int = 0
    max_tokens: int = 0
    compat_thinking_format: str | None = None
    identity_profile: OpenClawIdentityProfile
    source_persona_roles: list[str] = Field(default_factory=list)
    workflow_hints: list[str] = Field(default_factory=list)
    memory_instructions: list[str] = Field(default_factory=list)
    allowed_tool_classes: list[str] = Field(default_factory=list)
    escalation_rules: list[str] = Field(default_factory=list)
    professional_skills: list[SkillManifest] = Field(default_factory=list)
    general_skills: list[SkillManifest] = Field(default_factory=list)
    tool_profile: str
    sandbox_profile: str
    system_prompt: str


class OpenClawChatResult(BaseModel):
    employee_id: str
    openclaw_agent_id: str | None = None
    model_ref: str
    reply_text: str
    strategy: str = "fallback"
    session_key: str | None = None
    follow_up_texts: list[str] = Field(default_factory=list)
    handoff_targets: list[str] = Field(default_factory=list)
    handoff_reason: str | None = None
    turn_complete: bool = True
    turn_mode: str = "source"
    error_detail: str | None = None


class OpenClawHandoffContext(BaseModel):
    handoff_source_agent: str
    handoff_target_agent: str
    handoff_reason: str | None = None
    handoff_origin: str | None = None
    source_agent_visible_reply: str | None = None
    original_user_message: str
    thread_summary: str | None = None
    visible_turn_index: int | None = None
    retry_reason: str | None = None
    prior_target_reply: str | None = None
    collaboration_intent: str | None = None
    last_committed_state_summary: str | None = None
    pending_handoff_summary: str | None = None
    dispatch_reason: str | None = None
    interruption_reason: str | None = None
    spoken_bot_ids: list[str] = Field(default_factory=list)
    remaining_bot_ids: list[str] = Field(default_factory=list)
    remaining_turn_budget: int = 0


class OpenClawCollaborationContext(BaseModel):
    collaboration_intent: str | None = None
    dispatch_targets: list[str] = Field(default_factory=list)
    candidate_handoff_targets: list[str] = Field(default_factory=list)
    spoken_bot_ids: list[str] = Field(default_factory=list)
    remaining_bot_ids: list[str] = Field(default_factory=list)
    visible_turn_count: int = 0
    remaining_turn_budget: int = 0
    dispatch_reason: str | None = None
    last_committed_state_summary: str | None = None
    pending_handoff_summary: str | None = None
    interruption_mode: str | None = None
    retry_reason: str | None = None
    prior_reply_text: str | None = None


class OpenClawSemanticHandoffCandidate(BaseModel):
    employee_id: str
    confidence: float = 0.0
    reason: str | None = None


class OpenClawSemanticHandoffResult(BaseModel):
    needs_handoff: bool = False
    targets: list[OpenClawSemanticHandoffCandidate] = Field(default_factory=list)


class OpenClawProvisionSyncResult(BaseModel):
    runtime_home: str
    config_path: str
    workspace_root: str
    hooks_root: str
    workspace_count: int
    generated_file_count: int
    enabled_hooks: list[str] = Field(default_factory=list)


class OpenClawNativeSkillView(BaseModel):
    skill_id: str
    skill_name: str
    scope: str
    native_skill_name: str
    workspace_relative_dir: str
    workspace_relative_path: str
    runtime_relative_path: str | None = None
    source_ref: SkillSourceRef
    entrypoint_type: str
    fit_rationale: str | None = None
    exported: bool = True
    discovered: bool = True
    verification_status: str = "ready"
    discovery_detail: str | None = None


class OpenClawAgentDetailView(BaseModel):
    agent: OpenClawAgentConfig
    binding: OpenClawAgentBinding
    workspace_bundle: OpenClawWorkspaceBundle
    workspace_files: list[OpenClawWorkspaceFile] = Field(default_factory=list)
    native_skills: list[OpenClawNativeSkillView] = Field(default_factory=list)
    memory_namespaces: list[MemoryNamespace] = Field(default_factory=list)
    recent_memory_records: list[MemoryRecord] = Field(default_factory=list)
    recent_sessions: list["OpenClawGatewaySessionView"] = Field(default_factory=list)
    recent_runs: list["OpenClawGatewayRunView"] = Field(default_factory=list)


class OpenClawGatewayRuntimeModeView(BaseModel):
    runtime_mode: str
    gateway_base_url: str
    control_ui_url: str
    runtime_home: str


class OpenClawGatewayHealth(BaseModel):
    status: str
    runtime_mode: str
    gateway_base_url: str
    control_ui_url: str
    runtime_home: str
    config_path: str
    config_exists: bool
    reachable: bool
    active_session_refs: int = 0
    error_detail: str | None = None


class OpenClawGatewaySessionView(BaseModel):
    thread_id: str
    title: str
    surface: str
    channel_id: str
    status: str
    work_ticket_ref: str | None = None
    runtrace_ref: str | None = None
    active_runtrace_ref: str | None = None
    bound_agent_ids: list[str] = Field(default_factory=list)
    openclaw_session_refs: dict[str, str] = Field(default_factory=dict)
    visible_room_ref: str | None = None
    delivery_guard_epoch: int = 0
    pending_handoff_summary: str | None = None
    last_committed_state_summary: str | None = None


class OpenClawTranscriptEntryView(BaseModel):
    source: str
    actor: str
    text: str
    created_at: datetime
    app_id: str | None = None
    status: str | None = None
    source_kind: str | None = None
    dropped_as_stale: bool = False
    stale_drop_reason: str | None = None


class OpenClawGatewaySessionDetailView(BaseModel):
    thread_id: str
    title: str
    surface: str
    channel_id: str
    status: str
    work_ticket_ref: str | None = None
    runtrace_ref: str | None = None
    active_runtrace_ref: str | None = None
    taskgraph_ref: str | None = None
    bound_agent_ids: list[str] = Field(default_factory=list)
    participant_ids: list[str] = Field(default_factory=list)
    openclaw_session_refs: dict[str, str] = Field(default_factory=dict)
    visible_room_ref: str | None = None
    delivery_guard_epoch: int = 0
    superseded_runtrace_refs: list[str] = Field(default_factory=list)
    last_committed_state: dict[str, Any] = Field(default_factory=dict)
    pending_handoff: dict[str, Any] | None = None
    transcript_count: int = 0
    last_transcript_at: datetime | None = None
    transcript: list[OpenClawTranscriptEntryView] = Field(default_factory=list)
    recent_run_strategies: list[str] = Field(default_factory=list)


class OpenClawHookEntryView(BaseModel):
    hook_id: str
    enabled: bool
    source: str = "internal"
    config: dict[str, Any] = Field(default_factory=dict)


class OpenClawHookConfigView(BaseModel):
    runtime_home: str
    config_path: str
    internal_enabled: bool
    entries: list[OpenClawHookEntryView] = Field(default_factory=list)


class OpenClawControlUiTokenSetupView(BaseModel):
    runtime_mode: str
    control_ui_url: str
    launch_url: str
    token_configured: bool
    token_env_key: str
    token_source: str
    pairing_ready: bool = False
    setup_steps: list[str] = Field(default_factory=list)


class OpenClawGatewayRunView(BaseModel):
    runtrace_id: str
    work_ticket_ref: str
    thread_ref: str | None = None
    surface: str
    interaction_mode: str
    status: str
    model_ref: str
    strategy: str
    session_refs: dict[str, str] = Field(default_factory=dict)
    handoff_count: int = 0
    latest_handoff_targets: list[str] = Field(default_factory=list)
    latest_handoff_source_agent: str | None = None
    latest_handoff_reason: str | None = None
    handoff_origin: str | None = None
    handoff_resolution_basis: str | None = None
    collaboration_intent: str | None = None
    structured_handoff_targets: list[str] = Field(default_factory=list)
    reply_visible_named_targets: list[str] = Field(default_factory=list)
    reply_name_targets: list[str] = Field(default_factory=list)
    reply_semantic_handoff_targets: list[str] = Field(default_factory=list)
    final_handoff_targets: list[str] = Field(default_factory=list)
    handoff_contract_violation: bool = False
    handoff_repetition_violation: bool = False
    supersedes_runtrace_ref: str | None = None
    superseded_by_runtrace_ref: str | None = None
    visible_turn_count: int = 0
    delivery_guard_epoch: int = 0
    interruption_reason: str | None = None
    interruption_dispatch_targets: list[str] = Field(default_factory=list)
    turn_limit_scope: str = "run"
    spoken_bot_ids: list[str] = Field(default_factory=list)
    remaining_bot_ids: list[str] = Field(default_factory=list)
    remaining_turn_budget: int = 0
    stop_reason: str | None = None
    stopped_by_turn_limit: bool = False
    latest_turn_mode: str | None = None
    last_event_at: datetime
    error_detail: str | None = None


class OpenClawRunEventView(BaseModel):
    event_type: str
    message: str
    created_at: datetime
    metadata: dict[str, str] = Field(default_factory=dict)


class OpenClawGatewayRunDetailView(BaseModel):
    runtrace_id: str
    work_ticket_ref: str
    thread_ref: str | None = None
    taskgraph_ref: str | None = None
    surface: str
    interaction_mode: str
    status: str
    trigger_type: str
    model_ref: str
    strategy: str
    dispatch_targets: list[str] = Field(default_factory=list)
    agent_turn_refs: list[str] = Field(default_factory=list)
    activated_departments: list[str] = Field(default_factory=list)
    visible_speakers: list[str] = Field(default_factory=list)
    session_refs: dict[str, str] = Field(default_factory=dict)
    handoff_origin: str | None = None
    handoff_resolution_basis: str | None = None
    collaboration_intent: str | None = None
    structured_handoff_targets: list[str] = Field(default_factory=list)
    reply_visible_named_targets: list[str] = Field(default_factory=list)
    reply_name_targets: list[str] = Field(default_factory=list)
    reply_semantic_handoff_targets: list[str] = Field(default_factory=list)
    final_handoff_targets: list[str] = Field(default_factory=list)
    handoff_contract_violation: bool = False
    handoff_repetition_violation: bool = False
    supersedes_runtrace_ref: str | None = None
    superseded_by_runtrace_ref: str | None = None
    visible_turn_count: int = 0
    delivery_guard_epoch: int = 0
    interruption_reason: str | None = None
    interruption_dispatch_targets: list[str] = Field(default_factory=list)
    turn_limit_scope: str = "run"
    spoken_bot_ids: list[str] = Field(default_factory=list)
    remaining_bot_ids: list[str] = Field(default_factory=list)
    remaining_turn_budget: int = 0
    stop_reason: str | None = None
    stopped_by_turn_limit: bool = False
    latest_turn_mode: str | None = None
    handoff_source_reply: str | None = None
    handoff_target_reply: str | None = None
    last_event_at: datetime
    event_count: int = 0
    error_detail: str | None = None
    events: list[OpenClawRunEventView] = Field(default_factory=list)


class OpenClawOpsIssueView(BaseModel):
    source: str
    severity: str
    title: str
    detail: str
    ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
