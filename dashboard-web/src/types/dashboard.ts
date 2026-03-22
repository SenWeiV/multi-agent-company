export type JsonValue = string | number | boolean | null | JsonObject | JsonValue[]

export interface JsonObject {
  [key: string]: JsonValue
}

export interface RuntimeConfig {
  apiPrefix: string
  appName: string
  appEnv: string
}

export interface WorkTicket {
  ticket_id: string
  title: string
  status: string
  ticket_type: string
  channel_ref?: string | null
  thread_ref?: string | null
  taskgraph_ref?: string | null
  runtrace_ref?: string | null
  artifacts?: string[]
  [key: string]: unknown
}

export interface Checkpoint {
  checkpoint_id: string
  kind: string
  verdict_state?: string | null
  approval_state?: string | null
  [key: string]: unknown
}

export interface ConversationThread {
  thread_id: string
  title: string
  surface: string
  status: string
  channel_id: string
  participant_ids?: string[]
  bound_agent_ids?: string[]
  openclaw_session_refs?: Record<string, string>
  transcript?: TranscriptEntry[]
  [key: string]: unknown
}

export interface TranscriptEntry {
  actor: string
  text: string
  created_at: string
}

export interface EmployeePackSummary {
  employee_id: string
  employee_name: string
  department: string
  summary: string
  source_persona_packs: Array<{ role_name: string }>
  professional_skills?: SkillManifest[]
  general_skills?: SkillManifest[]
  [key: string]: unknown
}

export interface SkillSourceRef {
  repo_url: string
  repo_name: string
  commit_sha: string
  path: string
  license: string
  install_method: string
  verify_command: string
  local_path: string
}

export interface SkillManifest {
  skill_id: string
  skill_name: string
  summary: string
  scope: "professional" | "general"
  role_owner?: string | null
  source_ref: SkillSourceRef
  entrypoint_type: "instructional_skill" | "tool_backed_skill"
  invocation_contract?: Record<string, JsonValue>
  dependencies?: string[]
  tags?: string[]
  fit_rationale?: string | null
  enabled?: boolean
}

export interface SkillInvocationRecord {
  invocation_id: string
  employee_id: string
  skill_id: string
  scope: "professional" | "general"
  status: "ready" | "failed"
  detail?: string | null
  created_at: string
}

export interface SkillValidationIssue {
  employee_id?: string | null
  skill_id?: string | null
  issue_type: string
  detail: string
}

export interface SkillCatalogValidationResult {
  ok: boolean
  professional_skill_count_by_employee: Record<string, number>
  general_skill_count_by_employee: Record<string, number>
  issues: SkillValidationIssue[]
}

export interface MemoryNamespace {
  namespace_id: string
  scope: string
  [key: string]: unknown
}

export interface MemoryRecord {
  memory_id: string
  namespace_id: string
  scope: string
  kind: string
  content: string
  tags?: string[]
  created_at?: string
  [key: string]: unknown
}

export interface ArtifactBlob {
  source_type: string
  bucket: string
  summary: string
  object_key: string
  [key: string]: unknown
}

export interface FeishuBotApp {
  app_id: string
  employee_id: string
  display_name?: string | null
  bot_open_id?: string | null
  [key: string]: unknown
}

export interface ChannelBinding {
  binding_id: string
  provider: string
  surface: string
  default_route: string
  mention_policy: string
  sync_back_policy: string
  room_policy_ref?: string | null
  [key: string]: unknown
}

export interface BotSeatBinding {
  binding_id: string
  virtual_employee: string
  [key: string]: unknown
}

export interface RoomPolicy {
  room_policy_id: string
  room_type: string
  speaker_mode: string
  visible_participants: string[]
  turn_taking_rule: string
  escalation_rule: string
  [key: string]: unknown
}

export interface FeishuInboundEvent {
  app_id: string
  surface: string
  chat_id: string
  dispatch_mode?: string | null
  dispatch_targets?: string[]
  dispatch_resolution_basis?: string | null
  collaboration_intent?: string | null
  target_agent_ids?: string[]
  deterministic_name_target_ids?: string[]
  semantic_dispatch_target_ids?: string[]
  deterministic_text_target_ids?: string[]
  semantic_handoff_target_ids?: string[]
  forced_handoff_targets?: string[]
  raw_mentions_summary?: string[]
  work_ticket_ref?: string | null
  [key: string]: unknown
}

export interface FeishuGroupDebugEvent {
  debug_event_id: string
  app_id: string
  message_id: string
  chat_id: string
  surface: string
  sender_id?: string | null
  text?: string | null
  raw_mentions_summary?: string[]
  dispatch_targets?: string[]
  dispatch_resolution_basis?: string | null
  collaboration_intent?: string | null
  target_agent_ids?: string[]
  deterministic_name_target_ids?: string[]
  semantic_dispatch_target_ids?: string[]
  deterministic_text_target_ids?: string[]
  semantic_handoff_target_ids?: string[]
  semantic_handoff_candidates?: JsonObject[]
  matched_employee_id?: string | null
  match_basis?: string | null
  target_resolution_basis?: string | null
  dispatch_mode?: string | null
  processed_status: string
  detail?: string | null
  captured_at?: string
  [key: string]: unknown
}

export interface FeishuOutboundMessage {
  outbound_id: string
  app_id: string
  source_kind: string
  status: string
  receive_id: string
  receive_id_type: string
  text: string
  attempt_count?: number
  replay_attempt_count?: number
  error_detail?: string | null
  attachment_object_ref?: string | null
  work_ticket_ref?: string | null
  thread_ref?: string | null
  runtrace_ref?: string | null
  created_at?: string
  replay_source_outbound_ref?: string | null
  replay_root_outbound_ref?: string | null
  [key: string]: unknown
}

export interface FeishuDeadLetterDetail {
  dead_letter: FeishuOutboundMessage
  replay_history: FeishuOutboundMessage[]
}

export interface OpenClawGatewayHealth {
  status: string
  reachable: boolean
  gateway_base_url?: string | null
  config_path: string
  active_session_refs?: number
  error_detail?: string | null
}

export interface OpenClawRuntimeModeView {
  runtime_mode: string
  gateway_base_url?: string | null
  runtime_home: string
  control_ui_url: string
}

export interface OpenClawTokenSetupView {
  token_source: string
  token_env_key: string
  token_configured: boolean
  pairing_ready: boolean
  runtime_mode: string
  launch_url: string
  control_ui_url: string
  setup_steps: string[]
}

export interface OpenClawSessionView {
  thread_id: string
  title: string
  channel_id: string
  surface: string
  status: string
  work_ticket_ref?: string | null
  openclaw_session_refs?: Record<string, string>
}

export interface OpenClawSessionDetail extends OpenClawSessionView {
  runtrace_ref?: string | null
  taskgraph_ref?: string | null
  transcript_count?: number
  last_transcript_at?: string | null
  transcript?: TranscriptEntry[]
  bound_agent_ids?: string[]
  participant_ids?: string[]
  recent_run_strategies?: string[]
}

export interface OpenClawRunView {
  runtrace_id: string
  work_ticket_ref: string
  thread_ref?: string | null
  taskgraph_ref?: string | null
  model_ref: string
  strategy: string
  status: string
  surface: string
  interaction_mode: string
  handoff_count?: number
  latest_handoff_targets?: string[]
  latest_handoff_source_agent?: string | null
  latest_handoff_reason?: string | null
  handoff_origin?: string | null
  handoff_resolution_basis?: string | null
  collaboration_intent?: string | null
  structured_handoff_targets?: string[]
  reply_visible_named_targets?: string[]
  reply_name_targets?: string[]
  reply_semantic_handoff_targets?: string[]
  final_handoff_targets?: string[]
  handoff_contract_violation?: boolean
  handoff_repetition_violation?: boolean
  spoken_bot_ids?: string[]
  remaining_bot_ids?: string[]
  remaining_turn_budget?: number
  stop_reason?: string | null
  stopped_by_turn_limit?: boolean
  latest_turn_mode?: string | null
  last_event_at: string
  error_detail?: string | null
  session_refs?: Record<string, string>
}

export interface OpenClawRunDetail extends OpenClawRunView {
  handoff_source_reply?: string | null
  handoff_target_reply?: string | null
  events?: Array<{
    event_type: string
    message: string
    created_at?: string
  }>
}

export interface OpenClawHookEntry {
  hook_id: string
  source: string
  enabled: boolean
  config?: Record<string, JsonValue>
}

export interface OpenClawHooksView {
  entries: OpenClawHookEntry[]
}

export interface OpenClawOpsIssue {
  issue_id?: string
  severity?: string
  summary?: string
  message?: string
  [key: string]: unknown
}

export interface OpenClawAgentBinding {
  employee_id: string
  openclaw_agent_id: string
  workspace_home_ref: string
  workspace_path?: string
  agent_dir?: string
  primary_model_ref?: string
  tool_profile: string
  sandbox_profile: string
  channel_accounts?: Record<string, string>
}

export interface OpenClawWorkspaceBundle {
  employee_id: string
  bootstrap_entrypoint: string
  workspace_path: string
  bootstrap_files: Array<{ path?: string; filename?: string; name?: string }>
  channel_accounts?: Record<string, string>
}

export interface OpenClawIdentityProfile {
  identity: string
  soul?: string[]
  reply_style?: string[]
  guardrails?: string[]
  role_charter?: string[]
  decision_lens?: string[]
  preferred_deliverables?: string[]
  anti_patterns?: string[]
  handoff_style?: string[]
  escalation_triggers?: string[]
  role_boundaries?: string[]
  collaboration_rules?: string[]
  negative_instructions?: string[]
}

export interface OpenClawAgentConfigDetail {
  employee_id: string
  employee_name: string
  department: string
  openclaw_agent_id: string
  primary_model_ref: string
  provider_name: string
  provider_base_url: string
  model_id: string
  model_name: string
  tool_profile: string
  sandbox_profile: string
  source_persona_roles?: string[]
  workflow_hints?: string[]
  memory_instructions?: string[]
  identity_profile: OpenClawIdentityProfile
  professional_skills?: SkillManifest[]
  general_skills?: SkillManifest[]
  system_prompt: string
}

export interface OpenClawWorkspaceFile {
  path: string
  content: string
}

export interface OpenClawNativeSkill {
  skill_id: string
  skill_name: string
  scope: "professional" | "general" | string
  native_skill_name: string
  workspace_relative_dir: string
  workspace_relative_path: string
  runtime_relative_path?: string | null
  source_ref: SkillSourceRef
  entrypoint_type: "instructional_skill" | "tool_backed_skill" | string
  fit_rationale?: string | null
  exported: boolean
  discovered: boolean
  verification_status: string
  discovery_detail?: string | null
}

export interface OpenClawAgentDetail {
  agent: OpenClawAgentConfigDetail
  binding: OpenClawAgentBinding
  workspace_bundle: OpenClawWorkspaceBundle
  workspace_files: OpenClawWorkspaceFile[]
  native_skills: OpenClawNativeSkill[]
  memory_namespaces: MemoryNamespace[]
  recent_memory_records: MemoryRecord[]
  recent_sessions: OpenClawSessionView[]
  recent_runs: OpenClawRunView[]
}

export interface TicketDetailBundle {
  ticket: WorkTicket
  checkpoints: Checkpoint[]
  memories: MemoryRecord[]
  artifacts: ArtifactBlob[]
  thread: ConversationThread | null
  taskGraph: unknown | null
  runTrace: unknown | null
}

export interface DashboardCollections {
  tickets: WorkTicket[]
  threads: ConversationThread[]
  employeePacks: EmployeePackSummary[]
  namespaces: MemoryNamespace[]
  feishuBots: FeishuBotApp[]
  channelBindings: ChannelBinding[]
  botSeatBindings: BotSeatBinding[]
  roomPolicies: RoomPolicy[]
  feishuInbound: FeishuInboundEvent[]
  feishuGroupDebug: FeishuGroupDebugEvent[]
  feishuOutbound: FeishuOutboundMessage[]
  feishuDeadLetters: FeishuOutboundMessage[]
  feishuReplayAudit: FeishuOutboundMessage[]
  openclawGatewayHealth: OpenClawGatewayHealth | null
  openclawRuntimeMode: OpenClawRuntimeModeView | null
  openclawTokenSetup: OpenClawTokenSetupView | null
  openclawSessions: OpenClawSessionView[]
  openclawRecentRuns: OpenClawRunView[]
  openclawHooks: OpenClawHooksView | null
  openclawIssues: OpenClawOpsIssue[]
  openclawBindings: OpenClawAgentBinding[]
  openclawWorkspaceBundles: OpenClawWorkspaceBundle[]
  skillCatalogValidation: SkillCatalogValidationResult | null
  skillInvocations: SkillInvocationRecord[]
  postLaunchSummary: PostLaunchSummary | null
}

export interface DashboardSelectionState {
  selectedTicketId: string | null
  selectedThreadId: string | null
  selectedDeadLetterId: string | null
  selectedOpenClawThreadId: string | null
  selectedOpenClawRunId: string | null
}

export interface DashboardDetails {
  ticketDetail: TicketDetailBundle | null
  selectedThreadDetail: ConversationThread | null
  feishuDeadLetterDetail: FeishuDeadLetterDetail | null
  openclawSessionDetail: OpenClawSessionDetail | null
  openclawRunDetail: OpenClawRunDetail | null
}

export interface DashboardNotice {
  tone: "success" | "warning" | "destructive" | "default"
  message: string
  detail?: string
}

export interface PostLaunchFollowUpLink {
  source_work_ticket_ref: string
  source_title: string
  source_runtrace_ref: string
  follow_up_ticket_ref: string
  follow_up_title: string
  follow_up_runtrace_ref?: string | null
  follow_up_thread_ref?: string | null
  trigger_type: string
  created_at: string
  status: string
  note?: string
}

export interface PostLaunchSummary {
  launch_tickets: WorkTicket[]
  follow_ups: PostLaunchFollowUpLink[]
  feedback_memories: MemoryRecord[]
}

export interface PostLaunchRoutingResult {
  already_exists: boolean
  link: PostLaunchFollowUpLink
  follow_up_work_ticket: WorkTicket
  follow_up_run_trace: JsonObject
  follow_up_task_graph?: JsonObject | null
  follow_up_thread?: ConversationThread | null
}
