import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react"
import { toast } from "sonner"

import {
  apiRequest,
  fetchDashboardCollections,
  fetchDeadLetterDetail,
  fetchOpenClawRunDetail,
  fetchOpenClawSessionDetail,
  fetchThreadDetail,
  fetchTicketDetail,
  getRuntimeConfig,
  routePostLaunchFollowUp,
} from "@/lib/api"
import { parseCommaList, statusTone } from "@/lib/utils"
import type {
  ChannelBinding,
  DashboardCollections,
  DashboardDetails,
  DashboardNotice,
  DashboardSelectionState,
  OpenClawAgentBinding,
  RuntimeConfig,
  RoomPolicy,
  WorkTicket,
} from "@/types/dashboard"

const emptyCollections: DashboardCollections = {
  tickets: [],
  threads: [],
  employeePacks: [],
  namespaces: [],
  feishuBots: [],
  channelBindings: [],
  botSeatBindings: [],
  roomPolicies: [],
  feishuInbound: [],
  feishuGroupDebug: [],
  feishuOutbound: [],
  feishuDeadLetters: [],
  feishuReplayAudit: [],
  openclawGatewayHealth: null,
  openclawRuntimeMode: null,
  openclawTokenSetup: null,
  openclawSessions: [],
  openclawRecentRuns: [],
  openclawHooks: null,
  openclawIssues: [],
  openclawBindings: [],
  openclawWorkspaceBundles: [],
  skillCatalogValidation: null,
  skillInvocations: [],
  postLaunchSummary: null,
}

const emptySelection: DashboardSelectionState = {
  selectedTicketId: null,
  selectedThreadId: null,
  selectedDeadLetterId: null,
  selectedOpenClawThreadId: null,
  selectedOpenClawRunId: null,
}

const emptyDetails: DashboardDetails = {
  ticketDetail: null,
  selectedThreadDetail: null,
  feishuDeadLetterDetail: null,
  openclawSessionDetail: null,
  openclawRunDetail: null,
}

interface CreateIntakeInput {
  surface: string
  channelId: string
  boundAgentId?: string
  intent: string
}

interface SendFeishuInput {
  appId: string
  chatId: string
  text: string
  mentionEmployeeIds: string[]
}

interface DashboardContextValue {
  config: RuntimeConfig
  collections: DashboardCollections
  selection: DashboardSelectionState
  details: DashboardDetails
  notice: DashboardNotice | null
  isRefreshing: boolean
  isMutating: boolean
  refreshAll: () => Promise<void>
  selectTicket: (ticketId: string | null) => Promise<void>
  selectThread: (threadId: string | null) => Promise<void>
  selectDeadLetter: (outboundId: string | null) => Promise<void>
  selectOpenClawSession: (threadId: string | null) => Promise<void>
  selectOpenClawRun: (runtraceId: string | null) => Promise<void>
  createIntake: (input: CreateIntakeInput) => Promise<void>
  executeSelectedTicket: () => Promise<void>
  restoreSelectedTicket: () => Promise<void>
  sendFeishuTest: (input: SendFeishuInput) => Promise<void>
  replayDeadLetter: (outboundId: string) => Promise<void>
  updateChannelBinding: (bindingId: string, payload: Partial<ChannelBinding>) => Promise<void>
  updateRoomPolicy: (
    roomPolicyId: string,
    payload: Omit<Partial<RoomPolicy>, "visible_participants"> & { visible_participants?: string[] | string }
  ) => Promise<void>
  updateOpenClawBinding: (employeeId: string, payload: Partial<OpenClawAgentBinding>) => Promise<void>
  updateOpenClawHook: (hookId: string, payload: { enabled: boolean; config: Record<string, unknown> }) => Promise<void>
  syncOpenClawProvision: () => Promise<void>
  routeSelectedPostLaunchFollowUp: () => Promise<void>
  openControlUi: () => void
}

const DashboardContext = createContext<DashboardContextValue | null>(null)

function defaultChannelFor(surface: string, boundAgent?: string) {
  if (surface === "dashboard") return "dashboard:ceo"
  if (surface === "feishu_dm") return `feishu:dm:${boundAgent || "chief-of-staff"}`
  return "feishu:group:project-room"
}

function buildParticipantIds(surface: string, boundAgent?: string) {
  if (surface === "dashboard") {
    return ["ceo"]
  }
  if (surface === "feishu_dm") {
    return ["ceo", boundAgent ? `feishu-${boundAgent}` : "feishu-chief-of-staff"]
  }
  return ["ceo", "feishu-chief-of-staff", ...(boundAgent ? [`feishu-${boundAgent}`] : [])]
}

function pickSelection<T>(current: string | null, items: T[], getId: (item: T) => string, fallback?: string | null) {
  if (current && items.some((item) => getId(item) === current)) {
    return current
  }
  return fallback ?? null
}

export function DashboardProvider({ children }: PropsWithChildren) {
  const [collections, setCollections] = useState<DashboardCollections>(emptyCollections)
  const [selection, setSelection] = useState<DashboardSelectionState>(emptySelection)
  const [details, setDetails] = useState<DashboardDetails>(emptyDetails)
  const [notice, setNotice] = useState<DashboardNotice | null>(null)
  const [isRefreshing, setIsRefreshing] = useState(true)
  const [isMutating, setIsMutating] = useState(false)
  const config = useMemo(() => getRuntimeConfig(), [])

  const applyNotice = useCallback((message: string, detail?: string, tone: DashboardNotice["tone"] = "default") => {
    setNotice({ message, detail, tone })
    if (tone === "destructive") {
      toast.error(message, { description: detail })
      return
    }
    if (tone === "success") {
      toast.success(message, { description: detail })
      return
    }
    toast(message, { description: detail })
  }, [])

  const refreshAll = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const nextCollections = await fetchDashboardCollections()

      const nextSelection = {
        selectedTicketId: pickSelection(
          selection.selectedTicketId,
          nextCollections.tickets,
          (ticket) => ticket.ticket_id,
          nextCollections.tickets.at(-1)?.ticket_id ?? null
        ),
        selectedThreadId: pickSelection(
          selection.selectedThreadId,
          nextCollections.threads,
          (thread) => thread.thread_id,
          nextCollections.threads.at(-1)?.thread_id ?? null
        ),
        selectedDeadLetterId: pickSelection(
          selection.selectedDeadLetterId,
          nextCollections.feishuDeadLetters,
          (deadLetter) => deadLetter.outbound_id,
          nextCollections.feishuDeadLetters[0]?.outbound_id ?? null
        ),
        selectedOpenClawThreadId: pickSelection(
          selection.selectedOpenClawThreadId,
          nextCollections.openclawSessions,
          (session) => session.thread_id,
          nextCollections.openclawSessions[0]?.thread_id ?? null
        ),
        selectedOpenClawRunId: pickSelection(
          selection.selectedOpenClawRunId,
          nextCollections.openclawRecentRuns,
          (run) => run.runtrace_id,
          nextCollections.openclawRecentRuns[0]?.runtrace_id ?? null
        ),
      }

      const [ticketDetail, threadDetail, deadLetterDetail, sessionDetail, runDetail] = await Promise.all([
        nextSelection.selectedTicketId ? fetchTicketDetail(nextSelection.selectedTicketId).catch(() => null) : Promise.resolve(null),
        nextSelection.selectedThreadId ? fetchThreadDetail(nextSelection.selectedThreadId).catch(() => null) : Promise.resolve(null),
        nextSelection.selectedDeadLetterId ? fetchDeadLetterDetail(nextSelection.selectedDeadLetterId).catch(() => null) : Promise.resolve(null),
        nextSelection.selectedOpenClawThreadId
          ? fetchOpenClawSessionDetail(nextSelection.selectedOpenClawThreadId).catch(() => null)
          : Promise.resolve(null),
        nextSelection.selectedOpenClawRunId ? fetchOpenClawRunDetail(nextSelection.selectedOpenClawRunId).catch(() => null) : Promise.resolve(null),
      ])

      startTransition(() => {
        setCollections(nextCollections)
        setSelection(nextSelection)
        setDetails({
          ticketDetail,
          selectedThreadDetail: threadDetail,
          feishuDeadLetterDetail: deadLetterDetail,
          openclawSessionDetail: sessionDetail,
          openclawRunDetail: runDetail,
        })
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      applyNotice("刷新失败", message, "destructive")
    } finally {
      setIsRefreshing(false)
    }
  }, [applyNotice, selection])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  const selectTicket = useCallback(async (ticketId: string | null) => {
    setSelection((current) => ({ ...current, selectedTicketId: ticketId }))
    if (!ticketId) {
      setDetails((current) => ({ ...current, ticketDetail: null }))
      return
    }
    try {
      const ticketDetail = await fetchTicketDetail(ticketId)
      setDetails((current) => ({ ...current, ticketDetail }))
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      applyNotice("加载工单详情失败", message, "destructive")
      setDetails((current) => ({ ...current, ticketDetail: null }))
    }
  }, [applyNotice])

  const selectThread = useCallback(async (threadId: string | null) => {
    setSelection((current) => ({ ...current, selectedThreadId: threadId }))
    if (!threadId) {
      setDetails((current) => ({ ...current, selectedThreadDetail: null }))
      return
    }
    try {
      const threadDetail = await fetchThreadDetail(threadId)
      setDetails((current) => ({ ...current, selectedThreadDetail: threadDetail }))
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      applyNotice("加载线程详情失败", message, "destructive")
      setDetails((current) => ({ ...current, selectedThreadDetail: null }))
    }
  }, [applyNotice])

  const selectDeadLetter = useCallback(async (outboundId: string | null) => {
    setSelection((current) => ({ ...current, selectedDeadLetterId: outboundId }))
    if (!outboundId) {
      setDetails((current) => ({ ...current, feishuDeadLetterDetail: null }))
      return
    }
    try {
      const deadLetterDetail = await fetchDeadLetterDetail(outboundId)
      setDetails((current) => ({ ...current, feishuDeadLetterDetail: deadLetterDetail }))
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      applyNotice("加载 Feishu dead letter 详情失败", message, "destructive")
      setDetails((current) => ({ ...current, feishuDeadLetterDetail: null }))
    }
  }, [applyNotice])

  const selectOpenClawSession = useCallback(async (threadId: string | null) => {
    setSelection((current) => ({ ...current, selectedOpenClawThreadId: threadId }))
    if (!threadId) {
      setDetails((current) => ({ ...current, openclawSessionDetail: null }))
      return
    }
    try {
      const detail = await fetchOpenClawSessionDetail(threadId)
      setDetails((current) => ({ ...current, openclawSessionDetail: detail }))
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      applyNotice("加载 OpenClaw session 详情失败", message, "destructive")
      setDetails((current) => ({ ...current, openclawSessionDetail: null }))
    }
  }, [applyNotice])

  const selectOpenClawRun = useCallback(async (runtraceId: string | null) => {
    setSelection((current) => ({ ...current, selectedOpenClawRunId: runtraceId }))
    if (!runtraceId) {
      setDetails((current) => ({ ...current, openclawRunDetail: null }))
      return
    }
    try {
      const detail = await fetchOpenClawRunDetail(runtraceId)
      setDetails((current) => ({ ...current, openclawRunDetail: detail }))
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      applyNotice("加载 OpenClaw native run 详情失败", message, "destructive")
      setDetails((current) => ({ ...current, openclawRunDetail: null }))
    }
  }, [applyNotice])

  const mutateAndRefresh = useCallback(
    async (runner: () => Promise<unknown>, successMessage: string, detail?: string) => {
      setIsMutating(true)
      try {
        await runner()
        applyNotice(successMessage, detail, "success")
        await refreshAll()
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        applyNotice("操作失败", message, "destructive")
      } finally {
        setIsMutating(false)
      }
    },
    [applyNotice, refreshAll]
  )

  const createIntake = useCallback(
    async ({ surface, channelId, boundAgentId, intent }: CreateIntakeInput) => {
      const actualChannelId = channelId || defaultChannelFor(surface, boundAgentId)
      const response = await apiRequest<{
        command_result: { work_ticket: WorkTicket; classification: { interaction_mode: string } }
      }>("/conversations/intake", {
        method: "POST",
        body: JSON.stringify({
          surface,
          channel_id: actualChannelId,
          participant_ids: buildParticipantIds(surface, boundAgentId),
          bound_agent_ids: boundAgentId ? [boundAgentId] : [],
          command: { intent },
        }),
      })
      await refreshAll()
      await selectTicket(response.command_result.work_ticket.ticket_id)
      applyNotice(
        `${response.command_result.classification.interaction_mode} 已创建`,
        response.command_result.work_ticket.ticket_id,
        "success"
      )
    },
    [applyNotice, refreshAll, selectTicket]
  )

  const executeSelectedTicket = useCallback(async () => {
    const ticketId = details.ticketDetail?.ticket.ticket_id
    if (!ticketId) {
      applyNotice("请先选择一个可执行的 Work Ticket", undefined, "warning")
      return
    }
    await mutateAndRefresh(
      () => apiRequest(`/runtime/work-tickets/${ticketId}/execute`, { method: "POST" }),
      "Runtime 执行已触发",
      ticketId
    )
  }, [applyNotice, details.ticketDetail, mutateAndRefresh])

  const restoreSelectedTicket = useCallback(async () => {
    const checkpoints = details.ticketDetail?.checkpoints || []
    if (!checkpoints.length) {
      applyNotice("当前工单没有可恢复的 Checkpoint", undefined, "warning")
      return
    }
    const latest = checkpoints[checkpoints.length - 1]
    await mutateAndRefresh(
      () => apiRequest(`/control-plane/checkpoints/${latest.checkpoint_id}/restore`, { method: "POST" }),
      "Checkpoint 已恢复",
      latest.checkpoint_id
    )
  }, [applyNotice, details.ticketDetail, mutateAndRefresh])

  const sendFeishuTest = useCallback(async (input: SendFeishuInput) => {
    await mutateAndRefresh(
      () =>
        apiRequest("/feishu/send", {
          method: "POST",
          body: JSON.stringify({
            app_id: input.appId,
            chat_id: input.chatId,
            text: input.text,
            mention_employee_ids: input.mentionEmployeeIds,
          }),
        }),
      "Feishu 测试消息已发送",
      input.chatId
    )
  }, [mutateAndRefresh])

  const replayDeadLetter = useCallback(async (outboundId: string) => {
    await mutateAndRefresh(
      () => apiRequest(`/feishu/outbound-messages/${outboundId}/replay`, { method: "POST" }),
      "Dead letter 已重放",
      outboundId
    )
    await selectDeadLetter(outboundId)
  }, [mutateAndRefresh, selectDeadLetter])

  const updateChannelBinding = useCallback(
    async (bindingId: string, payload: Partial<ChannelBinding>) => {
      await mutateAndRefresh(
        () =>
          apiRequest(`/conversations/channel-bindings/${bindingId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          }),
        "Feishu channel binding 已更新",
        bindingId
      )
    },
    [mutateAndRefresh]
  )

  const updateRoomPolicy = useCallback(
    async (
      roomPolicyId: string,
      payload: Omit<Partial<RoomPolicy>, "visible_participants"> & { visible_participants?: string[] | string }
    ) => {
      await mutateAndRefresh(
        () =>
          apiRequest(`/conversations/room-policies/${roomPolicyId}`, {
            method: "PUT",
            body: JSON.stringify({
              ...payload,
              visible_participants: Array.isArray(payload.visible_participants)
                ? payload.visible_participants
                : parseCommaList(String(payload.visible_participants || "")),
            }),
          }),
        "Room policy 已更新",
        roomPolicyId
      )
    },
    [mutateAndRefresh]
  )

  const updateOpenClawBinding = useCallback(
    async (employeeId: string, payload: Partial<OpenClawAgentBinding>) => {
      await mutateAndRefresh(
        () =>
          apiRequest(`/openclaw/bindings/${employeeId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          }),
        "OpenClaw binding 已更新",
        employeeId
      )
    },
    [mutateAndRefresh]
  )

  const updateOpenClawHook = useCallback(
    async (hookId: string, payload: { enabled: boolean; config: Record<string, unknown> }) => {
      await mutateAndRefresh(
        () =>
          apiRequest(`/openclaw/gateway/hooks/${hookId}`, {
            method: "PUT",
            body: JSON.stringify(payload),
          }),
        "OpenClaw hook 已更新",
        hookId
      )
    },
    [mutateAndRefresh]
  )

  const syncOpenClawProvision = useCallback(async () => {
    await mutateAndRefresh(
      () => apiRequest("/openclaw/provision/sync", { method: "POST" }),
      "OpenClaw runtime home 已同步"
    )
  }, [mutateAndRefresh])

  const routeSelectedPostLaunchFollowUp = useCallback(async () => {
    const ticketId = details.ticketDetail?.ticket.ticket_id
    if (!ticketId) {
      applyNotice("请先选择一个 launch ticket", undefined, "warning")
      return
    }
    await mutateAndRefresh(
      () => routePostLaunchFollowUp(ticketId),
      "Post-launch cadence 已路由",
      ticketId
    )
  }, [applyNotice, details.ticketDetail, mutateAndRefresh])

  const openControlUi = useCallback(() => {
    window.open("/openclaw-control-ui/launch", "_blank", "noopener,noreferrer")
  }, [])

  const value = useMemo<DashboardContextValue>(
    () => ({
      config,
      collections,
      selection,
      details,
      notice,
      isRefreshing,
      isMutating,
      refreshAll,
      selectTicket,
      selectThread,
      selectDeadLetter,
      selectOpenClawSession,
      selectOpenClawRun,
      createIntake,
      executeSelectedTicket,
      restoreSelectedTicket,
      sendFeishuTest,
      replayDeadLetter,
      updateChannelBinding,
      updateRoomPolicy,
      updateOpenClawBinding,
      updateOpenClawHook,
      syncOpenClawProvision,
      routeSelectedPostLaunchFollowUp,
      openControlUi,
    }),
    [
      collections,
      config,
      createIntake,
      details,
      executeSelectedTicket,
      isMutating,
      isRefreshing,
      notice,
      openControlUi,
      refreshAll,
      replayDeadLetter,
      routeSelectedPostLaunchFollowUp,
      restoreSelectedTicket,
      selectDeadLetter,
      selectOpenClawRun,
      selectOpenClawSession,
      selectThread,
      selectTicket,
      selection,
      sendFeishuTest,
      syncOpenClawProvision,
      updateChannelBinding,
      updateOpenClawBinding,
      updateOpenClawHook,
      updateRoomPolicy,
    ]
  )

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
}

export function useDashboard() {
  const context = useContext(DashboardContext)
  if (!context) {
    throw new Error("useDashboard must be used inside DashboardProvider")
  }
  return context
}

export function useOverviewMetrics() {
  const { collections } = useDashboard()
  return useMemo(
    () => [
      {
        label: "Work Tickets",
        value: collections.tickets.length,
        tone: "default" as const,
      },
      {
        label: "Threads",
        value: collections.threads.length,
        tone: "default" as const,
      },
      {
        label: "Dead Letters",
        value: collections.feishuDeadLetters.length,
        tone: collections.feishuDeadLetters.length ? "warning" as const : "success" as const,
      },
      {
        label: "Native Runs",
        value: collections.openclawRecentRuns.length,
        tone: "default" as const,
      },
    ],
    [collections]
  )
}

export function useStatusSummary() {
  const { collections } = useDashboard()
  return useMemo(
    () => ({
      gatewayTone: statusTone(collections.openclawGatewayHealth?.status),
      gatewayStatus: collections.openclawGatewayHealth?.status || "unknown",
      runtimeMode: collections.openclawRuntimeMode?.runtime_mode || "compat",
      issueCount: collections.openclawIssues.length,
    }),
    [collections]
  )
}
