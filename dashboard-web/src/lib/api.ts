import type {
  ArtifactBlob,
  BotSeatBinding,
  ChannelBinding,
  ConversationThread,
  DashboardCollections,
  EmployeePackSummary,
  FeishuBotApp,
  FeishuDeadLetterDetail,
  FeishuGroupDebugEvent,
  FeishuInboundEvent,
  FeishuOutboundMessage,
  MemoryNamespace,
  MemoryRecord,
  OpenClawAgentBinding,
  OpenClawAgentDetail,
  OpenClawHooksView,
  OpenClawOpsIssue,
  OpenClawRunDetail,
  OpenClawRunView,
  OpenClawSessionDetail,
  OpenClawSessionView,
  OpenClawTokenSetupView,
  OpenClawWorkspaceBundle,
  RoomPolicy,
  RuntimeConfig,
  SkillCatalogValidationResult,
  SkillInvocationRecord,
  WorkTicket,
  Checkpoint,
  OpenClawGatewayHealth,
  OpenClawRuntimeModeView,
  PostLaunchRoutingResult,
  PostLaunchSummary,
} from "@/types/dashboard"

declare global {
  interface Window {
    __dashboardConfig?: Partial<RuntimeConfig>
  }
}

const DEFAULT_CONFIG: RuntimeConfig = {
  apiPrefix: "/api/v1",
  appName: "One-Person Company",
  appEnv: "development",
}

function normalizeRuntimeValue(value: string | undefined, fallback: string): string {
  if (!value || value.startsWith("__")) {
    return fallback
  }
  return value
}

export function getRuntimeConfig(): RuntimeConfig {
  const config = window.__dashboardConfig || {}
  return {
    apiPrefix: normalizeRuntimeValue(config.apiPrefix, DEFAULT_CONFIG.apiPrefix),
    appName: normalizeRuntimeValue(config.appName, DEFAULT_CONFIG.appName),
    appEnv: normalizeRuntimeValue(config.appEnv, DEFAULT_CONFIG.appEnv),
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const config = getRuntimeConfig()
  const response = await fetch(`${config.apiPrefix}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `${response.status} ${response.statusText}`)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export async function fetchDashboardCollections(): Promise<DashboardCollections> {
  const [
    tickets,
    threads,
    employeePacks,
    namespaces,
    feishuBots,
    channelBindings,
    botSeatBindings,
    roomPolicies,
    feishuInbound,
    feishuGroupDebug,
    feishuOutbound,
    feishuDeadLetters,
    feishuReplayAudit,
    openclawGatewayHealth,
    openclawRuntimeMode,
    openclawTokenSetup,
    openclawSessions,
    openclawRecentRuns,
    openclawHooks,
    openclawIssues,
    openclawBindings,
    openclawWorkspaceBundles,
    skillCatalogValidation,
    skillInvocations,
    postLaunchSummary,
  ] = await Promise.all([
    apiRequest<WorkTicket[]>("/control-plane/work-tickets"),
    apiRequest<ConversationThread[]>("/conversations/threads"),
    apiRequest<EmployeePackSummary[]>("/persona/employee-packs?core_only=true"),
    apiRequest<MemoryNamespace[]>("/memory/namespaces"),
    apiRequest<FeishuBotApp[]>("/feishu/bot-apps"),
    apiRequest<ChannelBinding[]>("/conversations/channel-bindings"),
    apiRequest("/conversations/bot-seat-bindings"),
    apiRequest<RoomPolicy[]>("/conversations/room-policies"),
    apiRequest<FeishuInboundEvent[]>("/feishu/inbound-events?limit=12"),
    apiRequest<FeishuGroupDebugEvent[]>("/feishu/group-debug-events?limit=20"),
    apiRequest<FeishuOutboundMessage[]>("/feishu/outbound-messages?limit=12"),
    apiRequest<FeishuOutboundMessage[]>("/feishu/dead-letters?limit=12"),
    apiRequest<FeishuOutboundMessage[]>("/feishu/replay-audit?limit=20"),
    apiRequest<OpenClawGatewayHealth>("/openclaw/gateway/health"),
    apiRequest<OpenClawRuntimeModeView>("/openclaw/gateway/runtime-mode"),
    apiRequest<OpenClawTokenSetupView>("/openclaw/gateway/token-setup"),
    apiRequest<OpenClawSessionView[]>("/openclaw/gateway/sessions"),
    apiRequest<OpenClawRunView[]>("/openclaw/gateway/recent-runs"),
    apiRequest<OpenClawHooksView>("/openclaw/gateway/hooks"),
    apiRequest<OpenClawOpsIssue[]>("/openclaw/gateway/issues"),
    apiRequest<OpenClawAgentBinding[]>("/openclaw/bindings"),
    apiRequest<OpenClawWorkspaceBundle[]>("/openclaw/workspace-bundles"),
    apiRequest<SkillCatalogValidationResult>("/persona/skill-catalog/validate"),
    apiRequest<SkillInvocationRecord[]>("/persona/skill-invocations?limit=30"),
    apiRequest<PostLaunchSummary>("/runtime/post-launch/summary"),
  ])

  return {
    tickets,
    threads,
    employeePacks,
    namespaces,
    feishuBots,
    channelBindings,
    botSeatBindings: botSeatBindings as BotSeatBinding[],
    roomPolicies,
    feishuInbound,
    feishuGroupDebug,
    feishuOutbound,
    feishuDeadLetters,
    feishuReplayAudit,
    openclawGatewayHealth,
    openclawRuntimeMode,
    openclawTokenSetup,
    openclawSessions,
    openclawRecentRuns,
    openclawHooks,
    openclawIssues,
    openclawBindings,
    openclawWorkspaceBundles,
    skillCatalogValidation,
    skillInvocations,
    postLaunchSummary,
  }
}

export async function fetchTicketDetail(ticketId: string) {
  const ticket = await apiRequest<WorkTicket>(`/control-plane/work-tickets/${ticketId}`)
  const [checkpoints, memories, artifacts, thread, taskGraph, runTrace] = await Promise.all([
    apiRequest<Checkpoint[]>(`/control-plane/work-tickets/${ticketId}/checkpoints`),
    apiRequest<MemoryRecord[]>(`/memory/work-tickets/${ticketId}`),
    apiRequest<ArtifactBlob[]>(`/artifacts/work-tickets/${ticketId}/blobs`),
    ticket.thread_ref ? apiRequest<ConversationThread>(`/conversations/threads/${ticket.thread_ref}`) : Promise.resolve(null),
    ticket.taskgraph_ref ? apiRequest(`/control-plane/task-graphs/${ticket.taskgraph_ref}`) : Promise.resolve(null),
    ticket.runtrace_ref ? apiRequest(`/control-plane/run-traces/${ticket.runtrace_ref}`) : Promise.resolve(null),
  ])
  return {
    ticket,
    checkpoints,
    memories,
    artifacts,
    thread,
    taskGraph,
    runTrace,
  }
}

export async function fetchThreadDetail(threadId: string) {
  return apiRequest<ConversationThread>(`/conversations/threads/${threadId}`)
}

export async function fetchDeadLetterDetail(outboundId: string) {
  return apiRequest<FeishuDeadLetterDetail>(`/feishu/dead-letters/${outboundId}`)
}

export async function fetchOpenClawSessionDetail(threadId: string) {
  return apiRequest<OpenClawSessionDetail>(`/openclaw/gateway/sessions/${threadId}`)
}

export async function fetchOpenClawRunDetail(runtraceId: string) {
  return apiRequest<OpenClawRunDetail>(`/openclaw/gateway/recent-runs/${runtraceId}`)
}

export async function fetchOpenClawAgentDetail(employeeId: string) {
  return apiRequest<OpenClawAgentDetail>(`/openclaw/agents/${employeeId}/detail`)
}

export async function syncOpenClawAgent(employeeId: string) {
  return apiRequest<OpenClawAgentDetail>(`/openclaw/agents/${employeeId}/sync`, {
    method: "POST",
  })
}

export async function recheckOpenClawAgentSkills(employeeId: string) {
  return apiRequest<OpenClawAgentDetail>(`/openclaw/agents/${employeeId}/skills/recheck`, {
    method: "POST",
  })
}

export async function updateOpenClawWorkspaceFile(employeeId: string, path: string, content: string) {
  return apiRequest(`/openclaw/agents/${employeeId}/workspace-files/${encodeURIComponent(path)}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  })
}

export async function routePostLaunchFollowUp(ticketId: string) {
  return apiRequest<PostLaunchRoutingResult>(`/runtime/work-tickets/${ticketId}/route-post-launch-follow-up`, {
    method: "POST",
  })
}
