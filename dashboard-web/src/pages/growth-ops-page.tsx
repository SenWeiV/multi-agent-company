import { useMemo, useState } from "react"
import { type ColumnDef } from "@tanstack/react-table"
import { LifeBuoy, Rocket, Sparkles } from "lucide-react"

import { DataTable } from "@/components/shared/data-table"
import { MetricCard } from "@/components/shared/metric-card"
import { StatusBadge } from "@/components/shared/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useDashboard } from "@/context/dashboard-context"
import { formatDateTime } from "@/lib/utils"
import type { MemoryRecord, PostLaunchFollowUpLink, RoomPolicy, WorkTicket } from "@/types/dashboard"

const POST_LAUNCH_TAGS = new Set([
  "post_launch_feedback",
  "growth_plan",
  "support_readiness",
  "feedback_loop",
  "partner_motion",
  "risk_review",
])

export function GrowthOpsPage() {
  const {
    collections,
    details,
    selection,
    selectTicket,
    routeSelectedPostLaunchFollowUp,
  } = useDashboard()
  const summary = collections.postLaunchSummary
  const [ticketQuery, setTicketQuery] = useState("")
  const [ticketStatusFilter, setTicketStatusFilter] = useState("all")
  const [followUpQuery, setFollowUpQuery] = useState("")
  const [followUpStatusFilter, setFollowUpStatusFilter] = useState("all")
  const [feedbackTagFilter, setFeedbackTagFilter] = useState("all")

  const ticketColumns = useMemo<ColumnDef<WorkTicket>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Launch Ticket",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.title}</div>
            <div className="text-xs text-slate-500">{row.original.ticket_type}</div>
          </div>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge value={row.original.status} />,
      },
      {
        accessorKey: "ticket_id",
        header: "ID",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.ticket_id}</code>,
      },
    ],
    []
  )

  const selectedTicket = details.ticketDetail?.ticket || null
  const selectedLaunchMemories = (details.ticketDetail?.memories || []).filter((memory: MemoryRecord) =>
    (memory.tags || []).some((tag) => POST_LAUNCH_TAGS.has(tag))
  )
  const selectedRunTraceEvents = Array.isArray((details.ticketDetail?.runTrace as { events?: unknown[] } | null)?.events)
    ? (((details.ticketDetail?.runTrace as { events?: unknown[] }).events || []) as Array<Record<string, string>>)
    : []
  const relatedFollowUps = (summary?.follow_ups || []).filter(
    (link) =>
      link.source_work_ticket_ref === selectedTicket?.ticket_id ||
      link.follow_up_ticket_ref === selectedTicket?.ticket_id
  )

  const growthRoomPolicies = collections.roomPolicies.filter((policy: RoomPolicy) =>
    ["room-launch", "room-ops", "room-support"].includes(policy.room_policy_id)
  )
  const filteredLaunchTickets = (summary?.launch_tickets || []).filter((ticket) => {
    const statusMatches = ticketStatusFilter === "all" || ticket.status === ticketStatusFilter
    const textMatches =
      !ticketQuery.trim() ||
      `${ticket.title} ${ticket.ticket_id} ${ticket.ticket_type}`.toLowerCase().includes(ticketQuery.trim().toLowerCase())
    return statusMatches && textMatches
  })
  const filteredFollowUps = (summary?.follow_ups || []).filter((link) => {
    const statusMatches = followUpStatusFilter === "all" || link.status === followUpStatusFilter
    const textMatches =
      !followUpQuery.trim() ||
      `${link.source_title} ${link.follow_up_title} ${link.follow_up_ticket_ref}`.toLowerCase().includes(followUpQuery.trim().toLowerCase())
    return statusMatches && textMatches
  })
  const filteredFeedbackMemories = (summary?.feedback_memories || []).filter((memory) => {
    if (feedbackTagFilter === "all") {
      return true
    }
    return (memory.tags || []).includes(feedbackTagFilter)
  })
  const filteredTraceEvents = selectedRunTraceEvents.filter((event) =>
    ["launch_feedback_synced", "post_launch_followup_created", "runtime_execution_completed"].includes(event.event_type || "")
  )

  const launchStatuses = Array.from(new Set((summary?.launch_tickets || []).map((ticket) => ticket.status))).sort()
  const followUpStatuses = Array.from(new Set((summary?.follow_ups || []).map((link) => link.status))).sort()
  const feedbackTags = Array.from(
    new Set((summary?.feedback_memories || []).flatMap((memory) => (memory.tags || []).filter((tag) => POST_LAUNCH_TAGS.has(tag))))
  ).sort()
  const latestLaunchTicket = filteredLaunchTickets[0] || summary?.launch_tickets[0] || null

  const metrics = [
    {
      label: "Launch Tickets",
      value: filteredLaunchTickets.length,
      eyebrow: `${summary?.launch_tickets.length || 0} total`,
    },
    {
      label: "Cadence Follow-ups",
      value: filteredFollowUps.length,
      eyebrow: `${summary?.follow_ups.length || 0} total`,
    },
    {
      label: "Feedback Memories",
      value: filteredFeedbackMemories.length,
      eyebrow: `${summary?.feedback_memories.length || 0} total`,
    },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      <section className="grid gap-4 lg:grid-cols-[1.35fr,0.95fr]">
        <Card className="glass-panel">
          <CardContent className="grid gap-6 p-6 lg:grid-cols-[1.25fr,0.95fr]">
            <div className="space-y-4">
              <span className="inline-flex rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">
                V1.5 Launch / Growth Loop
              </span>
              <div className="space-y-3">
                <h1 className="text-4xl font-semibold tracking-tight text-slate-950">
                  管理 launch tickets、post-launch cadence 和反馈回写。
                </h1>
                <p className="max-w-2xl text-base leading-7 text-slate-600">
                  这里聚合 `Launch / Growth Loop` 的主工单、自动创建的 cadence follow-up，以及回写到 Memory Fabric
                  的增长、支持与反馈记录。
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button onClick={() => void routeSelectedPostLaunchFollowUp()} disabled={!selection.selectedTicketId}>
                  <LifeBuoy className="h-4 w-4" />
                  Route Post-launch Cadence
                </Button>
                <Button variant="outline" onClick={() => void selectTicket(latestLaunchTicket?.ticket_id || null)}>
                  <Rocket className="h-4 w-4" />
                  打开最新 Launch Ticket
                </Button>
              </div>
            </div>

            <div className="grid gap-3">
              {metrics.map((metric) => (
                <MetricCard
                  key={metric.label}
                  label={metric.label}
                  value={metric.value}
                  eyebrow={metric.eyebrow}
                  accent={metric.label === "Cadence Follow-ups" && metric.value > 0}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card className="glass-panel">
            <CardHeader>
              <CardDescription>Feedback Stream</CardDescription>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-cyan-600" />
                最新 post-launch memories
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Select value={feedbackTagFilter} onValueChange={setFeedbackTagFilter}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部 feedback tags</SelectItem>
                  {feedbackTags.map((tag) => (
                    <SelectItem key={tag} value={tag}>
                      {tag}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <ScrollArea className="h-[260px] pr-3">
                <div className="space-y-3">
                  {filteredFeedbackMemories.slice(0, 8).map((memory) => (
                    <article key={memory.memory_id} className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-slate-950">{memory.namespace_id}</p>
                          <p className="text-xs text-slate-500">{formatDateTime(memory.created_at)}</p>
                        </div>
                        <StatusBadge value={memory.kind} />
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{memory.content}</p>
                    </article>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <Card className="glass-panel">
            <CardHeader>
              <CardDescription>Visible Communication Policies</CardDescription>
              <CardTitle>Growth / Support Rooms</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              {growthRoomPolicies.map((policy) => (
                <article key={policy.room_policy_id} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-950">{policy.room_type}</p>
                      <p className="text-xs text-slate-500">{policy.room_policy_id}</p>
                    </div>
                    <StatusBadge value={policy.speaker_mode} />
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">{policy.turn_taking_rule}</p>
                  <p className="mt-2 text-xs text-slate-500">visible: {policy.visible_participants.join(", ")}</p>
                </article>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

      <ResizablePanelGroup direction="horizontal" className="min-h-[760px] overflow-hidden rounded-[28px] border border-white/80 bg-white/50 shadow-panel">
        <ResizablePanel defaultSize={56} minSize={42}>
          <div className="grid h-full gap-4 p-4 lg:grid-cols-[1.05fr,0.95fr]">
            <Card className="glass-panel">
              <CardHeader className="space-y-4">
                <div>
                  <CardDescription>Launch Tickets</CardDescription>
                  <CardTitle>Recipe C 主工单</CardTitle>
                </div>
                <div className="grid gap-3 md:grid-cols-[1.2fr,0.8fr]">
                  <Input
                    value={ticketQuery}
                    onChange={(event) => setTicketQuery(event.target.value)}
                    placeholder="搜索工单标题 / ID / 类型"
                  />
                  <Select value={ticketStatusFilter} onValueChange={setTicketStatusFilter}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部状态</SelectItem>
                      {launchStatuses.map((status) => (
                        <SelectItem key={status} value={status}>
                          {status}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={ticketColumns}
                  data={filteredLaunchTickets}
                  selectedRowId={selection.selectedTicketId}
                  getRowId={(row) => row.ticket_id}
                  onRowClick={(row) => void selectTicket(row.ticket_id)}
                  emptyMessage="还没有 launch_growth 工单。"
                />
              </CardContent>
            </Card>

            <Card className="glass-panel">
              <CardHeader className="space-y-4">
                <div>
                  <CardDescription>Cadence Follow-ups</CardDescription>
                  <CardTitle>自动与手动路由结果</CardTitle>
                </div>
                <div className="grid gap-3 md:grid-cols-[1.2fr,0.8fr]">
                  <Input
                    value={followUpQuery}
                    onChange={(event) => setFollowUpQuery(event.target.value)}
                    placeholder="搜索 source / follow-up"
                  />
                  <Select value={followUpStatusFilter} onValueChange={setFollowUpStatusFilter}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部状态</SelectItem>
                      {followUpStatuses.map((status) => (
                        <SelectItem key={status} value={status}>
                          {status}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[620px] pr-3">
                  <div className="space-y-3">
                    {filteredFollowUps.length ? (
                      filteredFollowUps.map((link: PostLaunchFollowUpLink) => (
                        <article key={`${link.source_work_ticket_ref}:${link.follow_up_ticket_ref}`} className="rounded-2xl border border-slate-200 bg-white p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-medium text-slate-950">{link.follow_up_title}</p>
                              <p className="mt-1 text-sm text-slate-500">from {link.source_title}</p>
                            </div>
                            <StatusBadge value={link.status} />
                          </div>
                          <Separator className="my-3" />
                          <div className="space-y-2 text-xs text-slate-500">
                            <p>{link.follow_up_ticket_ref}</p>
                            <p>{formatDateTime(link.created_at)}</p>
                          </div>
                          <div className="mt-3 flex gap-2">
                            <Button variant="outline" size="sm" onClick={() => void selectTicket(link.source_work_ticket_ref)}>
                              Source
                            </Button>
                            <Button size="sm" onClick={() => void selectTicket(link.follow_up_ticket_ref)}>
                              Open Follow-up
                            </Button>
                          </div>
                        </article>
                      ))
                    ) : (
                      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-10 text-center text-sm text-slate-500">
                        当前筛选条件下没有 cadence follow-up。
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={44} minSize={30}>
          <div className="h-full border-l border-white/80 bg-white/90 p-4">
            <Card className="glass-panel h-full">
              <CardHeader className="border-b border-slate-200">
                <CardDescription>Growth / Support Inspector</CardDescription>
                <CardTitle>{selectedTicket?.title || "选择一个 launch 或 follow-up ticket"}</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Tabs defaultValue="overview" className="h-full">
                  <TabsList className="mx-4 mt-4 grid grid-cols-4">
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="feedback">Feedback</TabsTrigger>
                    <TabsTrigger value="followups">Follow-ups</TabsTrigger>
                    <TabsTrigger value="trace">Trace</TabsTrigger>
                  </TabsList>
                  <div className="px-4 pb-4 pt-3">
                    <TabsContent value="overview" className="space-y-3">
                      <Card className="subtle-outline">
                        <CardContent className="space-y-2 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium text-slate-950">{selectedTicket?.title || "未选择工单"}</p>
                            {selectedTicket ? <StatusBadge value={selectedTicket.status} /> : null}
                          </div>
                          {selectedTicket ? (
                            <>
                              <p className="text-sm text-slate-600">ticket_id: {selectedTicket.ticket_id}</p>
                              <p className="text-sm text-slate-600">channel: {selectedTicket.channel_ref || "n/a"}</p>
                            </>
                          ) : (
                            <p className="text-sm text-slate-500">选择 launch ticket 后查看 cadence 和反馈状态。</p>
                          )}
                        </CardContent>
                      </Card>
                    </TabsContent>
                    <TabsContent value="feedback" className="space-y-3">
                      {selectedLaunchMemories.length ? (
                        selectedLaunchMemories.map((memory) => (
                          <Card key={memory.memory_id} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{memory.namespace_id}</p>
                                <StatusBadge value={memory.kind} />
                              </div>
                              <p className="text-sm leading-6 text-slate-600">{memory.content}</p>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-10 text-center text-sm text-slate-500">
                          当前工单还没有专项 post-launch feedback memory。
                        </div>
                      )}
                    </TabsContent>
                    <TabsContent value="followups" className="space-y-3">
                      {relatedFollowUps.length ? (
                        relatedFollowUps.map((link) => (
                          <Card key={`${link.source_work_ticket_ref}:${link.follow_up_ticket_ref}`} className="subtle-outline">
                            <CardContent className="space-y-3 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{link.follow_up_title}</p>
                                <StatusBadge value={link.status} />
                              </div>
                              <div className="space-y-1 text-sm text-slate-600">
                                <p>source: {link.source_work_ticket_ref}</p>
                                <p>follow-up: {link.follow_up_ticket_ref}</p>
                              </div>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-10 text-center text-sm text-slate-500">
                          当前工单还没有 follow-up 关联。
                        </div>
                      )}
                    </TabsContent>
                    <TabsContent value="trace" className="space-y-3">
                      {filteredTraceEvents.length ? (
                        filteredTraceEvents.map((event, index) => (
                          <Card key={`${event.event_type || index}`} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{event.event_type}</p>
                                <span className="text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
                              </div>
                              <p className="text-sm leading-6 text-slate-600">{event.message}</p>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/70 px-4 py-10 text-center text-sm text-slate-500">
                          当前工单还没有 launch-specific trace event。
                        </div>
                      )}
                    </TabsContent>
                  </div>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
