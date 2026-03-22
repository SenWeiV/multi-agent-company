import { useMemo, useState } from "react"
import { type ColumnDef } from "@tanstack/react-table"
import { LifeBuoy } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { DataTable } from "@/components/shared/data-table"
import { JsonView } from "@/components/shared/json-view"
import { StatusBadge } from "@/components/shared/status-badge"
import { useDashboard } from "@/context/dashboard-context"
import { formatDateTime } from "@/lib/utils"
import type { EmployeePackSummary, MemoryRecord, WorkTicket } from "@/types/dashboard"

function nextDefaultChannel(surface: string, boundAgent?: string) {
  if (surface === "dashboard") return "dashboard:ceo"
  if (surface === "feishu_dm") return `feishu:dm:${boundAgent || "chief-of-staff"}`
  return "feishu:group:project-room"
}

export function ControlPlanePage() {
  const {
    collections,
    details,
    selection,
    createIntake,
    executeSelectedTicket,
    restoreSelectedTicket,
    routeSelectedPostLaunchFollowUp,
    selectTicket,
  } = useDashboard()
  const [surface, setSurface] = useState("dashboard")
  const [boundAgentId, setBoundAgentId] = useState("")
  const [channelId, setChannelId] = useState("dashboard:ceo")
  const [intent, setIntent] = useState("")

  const ticketColumns = useMemo<ColumnDef<WorkTicket>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Title",
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
        header: "Ticket ID",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.ticket_id}</code>,
      },
    ],
    []
  )

  const employeeColumns = useMemo<ColumnDef<EmployeePackSummary>[]>(
    () => [
      {
        accessorKey: "employee_name",
        header: "Employee",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.employee_name}</div>
            <div className="text-xs text-slate-500">{row.original.department}</div>
          </div>
        ),
      },
      {
        accessorKey: "summary",
        header: "Summary",
        cell: ({ row }) => <span className="line-clamp-2 text-sm text-slate-600">{row.original.summary}</span>,
      },
    ],
    []
  )

  const taskGraphNodes = Array.isArray((details.ticketDetail?.taskGraph as { nodes?: unknown[] } | null)?.nodes)
    ? (((details.ticketDetail?.taskGraph as { nodes?: unknown[] }).nodes || []) as Array<Record<string, string>>)
    : []
  const runTraceEvents = Array.isArray((details.ticketDetail?.runTrace as { events?: unknown[] } | null)?.events)
    ? (((details.ticketDetail?.runTrace as { events?: unknown[] }).events || []) as Array<Record<string, string>>)
    : []
  const workflowRecipe = String(
    (details.ticketDetail?.taskGraph as { workflow_recipe?: string } | null)?.workflow_recipe ||
      (details.ticketDetail?.runTrace as { workflow_recipe?: string } | null)?.workflow_recipe ||
      ""
  )
  const ticketMemories = details.ticketDetail?.memories || []
  const artifacts = details.ticketDetail?.artifacts || []
  const postLaunchFollowUpEvents = runTraceEvents.filter((event) => event.event_type === "post_launch_followup_created")

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">Control Plane</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">CEO Inbox、工单与执行详情</h1>
        <p className="text-slate-600">左侧发起新指令，中间浏览 Work Ticket，右侧通过 inspector 查看 TaskGraph、RunTrace、memory 与 artifact。</p>
      </div>

      <ResizablePanelGroup direction="horizontal" className="min-h-[820px] overflow-hidden rounded-[28px] border border-white/80 bg-white/50 shadow-panel">
        <ResizablePanel defaultSize={58} minSize={46}>
          <div className="grid h-full gap-4 p-4 lg:grid-cols-[0.95fr,1.15fr]">
            <div className="space-y-4">
              <Card className="glass-panel">
                <CardHeader>
                  <CardDescription>CEO Inbox</CardDescription>
                  <CardTitle>发起指令</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <span className="text-sm font-medium text-slate-600">Interaction surface</span>
                      <Select
                        value={surface}
                        onValueChange={(value) => {
                          setSurface(value)
                          setChannelId(nextDefaultChannel(value, boundAgentId))
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="dashboard">Dashboard</SelectItem>
                          <SelectItem value="feishu_dm">Feishu DM</SelectItem>
                          <SelectItem value="feishu_group">Feishu Group</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <span className="text-sm font-medium text-slate-600">Bound employee</span>
                      <Select
                        value={boundAgentId || "__auto__"}
                        onValueChange={(value) => {
                          const next = value === "__auto__" ? "" : value
                          setBoundAgentId(next)
                          setChannelId(nextDefaultChannel(surface, next))
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="__auto__">自动路由</SelectItem>
                          {collections.employeePacks.map((pack) => (
                            <SelectItem key={pack.employee_id} value={pack.employee_id}>
                              {pack.employee_name} · {pack.department}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <span className="text-sm font-medium text-slate-600">Channel ID</span>
                    <Input value={channelId} onChange={(event) => setChannelId(event.target.value)} />
                  </div>

                  <div className="space-y-2">
                    <span className="text-sm font-medium text-slate-600">Intent</span>
                    <Textarea
                      rows={8}
                      value={intent}
                      onChange={(event) => setIntent(event.target.value)}
                      placeholder="例如：梳理 OpenClaw native runtime 迁移后的 V1 发布检查清单"
                    />
                  </div>

                  <Button
                    className="w-full"
                    onClick={async () => {
                      if (!intent.trim()) return
                      await createIntake({
                        surface,
                        channelId,
                        boundAgentId: boundAgentId || undefined,
                        intent,
                      })
                      setIntent("")
                    }}
                  >
                    Create Thread + Intake
                  </Button>
                </CardContent>
              </Card>

              <Card className="glass-panel">
                <CardHeader>
                  <CardDescription>Core Employee Packs</CardDescription>
                  <CardTitle>核心席位</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable
                    columns={employeeColumns}
                    data={collections.employeePacks}
                    getRowId={(row) => row.employee_id}
                    emptyMessage="暂无 Employee Pack"
                  />
                </CardContent>
              </Card>
            </div>

            <Card className="glass-panel">
              <CardHeader>
                <CardDescription>Work Tickets</CardDescription>
                <CardTitle>工单列表</CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={ticketColumns}
                  data={[...collections.tickets].reverse()}
                  selectedRowId={selection.selectedTicketId}
                  getRowId={(row) => row.ticket_id}
                  onRowClick={(row) => void selectTicket(row.ticket_id)}
                  emptyMessage="还没有 Work Ticket"
                />
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={42} minSize={30}>
          <div className="h-full border-l border-white/80 bg-white/90 p-4">
            <Card className="glass-panel h-full">
              <CardHeader className="border-b border-slate-200">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardDescription>Execution Inspector</CardDescription>
                    <CardTitle>Selected Ticket</CardTitle>
                  </div>
                  <div className="flex gap-2">
                    {workflowRecipe === "launch_growth" ? (
                      <Button variant="outline" size="sm" onClick={() => void routeSelectedPostLaunchFollowUp()}>
                        <LifeBuoy className="h-4 w-4" />
                        Route Cadence
                      </Button>
                    ) : null}
                    <Button variant="outline" size="sm" onClick={() => void executeSelectedTicket()}>
                      Run Runtime
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => void restoreSelectedTicket()}>
                      Restore Checkpoint
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                <Tabs defaultValue="ticket" className="h-full">
                  <TabsList className="mx-4 mt-4 grid grid-cols-5">
                    <TabsTrigger value="ticket">Ticket</TabsTrigger>
                    <TabsTrigger value="taskgraph">TaskGraph</TabsTrigger>
                    <TabsTrigger value="runtrace">RunTrace</TabsTrigger>
                    <TabsTrigger value="memory">Memory</TabsTrigger>
                    <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
                  </TabsList>
                  <div className="px-4 pb-4 pt-3">
                    <TabsContent value="ticket" className="space-y-4">
                      <JsonView value={details.ticketDetail?.ticket} empty="选择一个工单查看详情。" />
                      {workflowRecipe === "launch_growth" ? (
                        <Card className="subtle-outline">
                          <CardContent className="space-y-3 p-4">
                            <div className="flex items-center justify-between gap-3">
                              <div>
                                <p className="font-medium text-slate-950">Post-launch Cadence</p>
                                <p className="text-sm text-slate-500">为 launch ticket 快速创建或查看 follow-up cadence。</p>
                              </div>
                              <Button size="sm" onClick={() => void routeSelectedPostLaunchFollowUp()}>
                                <LifeBuoy className="h-4 w-4" />
                                Route Follow-up
                              </Button>
                            </div>
                            {postLaunchFollowUpEvents.length ? (
                              <div className="space-y-2">
                                {postLaunchFollowUpEvents.map((event, index) => (
                                  <div
                                    key={`${event.event_type || "follow-up"}-${index}`}
                                    className="rounded-2xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-600"
                                  >
                                    <p className="font-medium text-slate-950">{event.message || "Cadence created"}</p>
                                    <p className="mt-1 break-all">
                                      follow_up_ticket_ref: {String((event as { metadata?: { follow_up_ticket_ref?: string } }).metadata?.follow_up_ticket_ref || "n/a")}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className="text-sm text-slate-500">当前 launch ticket 还没有 cadence follow-up。</p>
                            )}
                          </CardContent>
                        </Card>
                      ) : null}
                      <div className="grid gap-3 md:grid-cols-2">
                        {(details.ticketDetail?.checkpoints || []).map((checkpoint) => (
                          <Card key={checkpoint.checkpoint_id} className="subtle-outline">
                            <CardContent className="space-y-3 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <code className="rounded bg-slate-100 px-2 py-1 text-xs">{checkpoint.checkpoint_id}</code>
                                <StatusBadge value={checkpoint.kind} />
                              </div>
                              <div className="text-sm text-slate-600">
                                verdict: {checkpoint.verdict_state || "n/a"} · approval: {checkpoint.approval_state || "n/a"}
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </TabsContent>
                    <TabsContent value="taskgraph" className="space-y-3">
                      {taskGraphNodes.length ? (
                        taskGraphNodes.map((node, index) => (
                          <Card key={`${node.node_id || index}`} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{node.title || node.node_id || `Node ${index + 1}`}</p>
                                <StatusBadge value={node.status} />
                              </div>
                              <p className="text-sm text-slate-600">{node.owner_department || node.output_kind || "Execution node"}</p>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <JsonView value={details.ticketDetail?.taskGraph} empty="当前工单没有 TaskGraph。" />
                      )}
                    </TabsContent>
                    <TabsContent value="runtrace" className="space-y-3">
                      {runTraceEvents.length ? (
                        runTraceEvents.map((event, index) => (
                          <Card key={`${event.event_type || index}-${index}`} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{event.event_type || "event"}</p>
                                <span className="text-xs text-slate-500">{formatDateTime(event.created_at)}</span>
                              </div>
                              <p className="text-sm leading-6 text-slate-600">{event.message || "n/a"}</p>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <JsonView value={details.ticketDetail?.runTrace} empty="当前工单没有 RunTrace。" />
                      )}
                    </TabsContent>
                    <TabsContent value="memory" className="space-y-3">
                      {ticketMemories.length ? (
                        ticketMemories.map((memory: MemoryRecord) => (
                          <Card key={memory.memory_id} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{memory.scope} / {memory.kind}</p>
                                <code className="rounded bg-slate-100 px-2 py-1 text-xs">{memory.namespace_id}</code>
                              </div>
                              <p className="text-sm leading-6 text-slate-600">{memory.content}</p>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <JsonView value={null} empty="这个工单还没有 Memory 记录。" />
                      )}
                    </TabsContent>
                    <TabsContent value="artifacts" className="space-y-3">
                      {artifacts.length ? (
                        artifacts.map((artifact) => (
                          <Card key={artifact.object_key} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{artifact.source_type}</p>
                                <code className="rounded bg-slate-100 px-2 py-1 text-xs">{artifact.bucket}</code>
                              </div>
                              <p className="text-sm leading-6 text-slate-600">{artifact.summary}</p>
                              <code className="text-xs text-slate-500">{artifact.object_key}</code>
                            </CardContent>
                          </Card>
                        ))
                      ) : (
                        <JsonView value={null} empty="这个工单还没有 Artifact Blob。" />
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
