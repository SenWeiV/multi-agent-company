import { useMemo, useState } from "react"
import { type ColumnDef } from "@tanstack/react-table"
import { LifeBuoy, RefreshCcw } from "lucide-react"

import { DataTable } from "@/components/shared/data-table"
import { JsonView } from "@/components/shared/json-view"
import { StatusBadge } from "@/components/shared/status-badge"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useDashboard } from "@/context/dashboard-context"
import { cn, formatDateTime } from "@/lib/utils"
import type {
  JsonObject,
  OpenClawAgentBinding,
  OpenClawRunDetail,
  OpenClawRunView,
  OpenClawSessionDetail,
  OpenClawSessionView,
  OpenClawWorkspaceBundle,
  TranscriptEntry,
} from "@/types/dashboard"

function formatInlineList(values?: Array<string | null | undefined>, fallback = "none"): string {
  const normalized = (values || []).map((value) => value?.trim()).filter(Boolean) as string[]
  return normalized.length ? normalized.join(", ") : fallback
}

function compactJson(value?: JsonObject | null): string {
  if (!value || Object.keys(value).length === 0) {
    return "none"
  }
  return JSON.stringify(value)
}

function summarizePendingHandoff(value?: JsonObject | null): string {
  if (!value) {
    return "none"
  }
  const source = typeof value.source_agent_id === "string" ? value.source_agent_id : null
  const target = typeof value.target_agent_id === "string" ? value.target_agent_id : null
  const instruction = typeof value.instruction === "string" ? value.instruction : null
  const reason = typeof value.reason === "string" ? value.reason : null
  const pieces: string[] = []
  if (source || target) {
    pieces.push(`${source || "unknown"} -> ${target || "unknown"}`)
  }
  if (instruction) {
    pieces.push(`instruction=${instruction}`)
  }
  if (reason) {
    pieces.push(`reason=${reason}`)
  }
  return pieces.length ? pieces.join(" | ") : compactJson(value)
}

function DetailBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <div className="mt-3 space-y-2 text-sm text-slate-600">{children}</div>
    </div>
  )
}

function DetailItem({
  label,
  value,
  className,
}: {
  label: string
  value?: string | number | null
  className?: string
}) {
  return (
    <div className={cn("rounded-xl border border-white/80 bg-white px-3 py-2", className)}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-1 break-all text-sm text-slate-700">
        {label}: {value ?? "n/a"}
      </p>
    </div>
  )
}

function TranscriptSignalItem({ entry }: { entry: TranscriptEntry }) {
  return (
    <div
      className={cn(
        "rounded-2xl border px-3 py-3",
        entry.dropped_as_stale ? "border-rose-200 bg-rose-50/80" : "border-slate-200 bg-white"
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-slate-900">{entry.actor}</span>
        {entry.source ? <StatusBadge value={entry.source} /> : null}
        {entry.source_kind ? <StatusBadge value={entry.source_kind} /> : null}
        {entry.status ? <StatusBadge value={entry.status} /> : null}
        {entry.dropped_as_stale ? (
          <Badge variant="secondary" className="border-transparent bg-rose-100 text-rose-700 hover:bg-rose-100">
            stale dropped
          </Badge>
        ) : null}
        <span className="ml-auto text-xs text-slate-400">{formatDateTime(entry.created_at)}</span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-700">{entry.text}</p>
      {entry.stale_drop_reason ? <p className="mt-2 text-xs font-medium text-rose-700">{entry.stale_drop_reason}</p> : null}
    </div>
  )
}

function RunSummary({ run }: { run: OpenClawRunDetail }) {
  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <DetailBlock title="Run Signals">
          <div className="flex flex-wrap gap-2">
            <StatusBadge value={run.status} />
            <StatusBadge value={run.strategy} />
            {run.latest_turn_mode ? <StatusBadge value={run.latest_turn_mode} /> : null}
          </div>
          <DetailItem label="visible turns" value={run.visible_turn_count ?? 0} />
          <DetailItem label="remaining budget" value={run.remaining_turn_budget ?? 0} />
          <DetailItem label="delivery guard epoch" value={run.delivery_guard_epoch ?? 0} />
          <DetailItem label="stop reason" value={run.stop_reason} />
        </DetailBlock>
        <DetailBlock title="Supersede Chain">
          <DetailItem label="supersedes" value={run.supersedes_runtrace_ref} className="border-amber-100 bg-amber-50/80" />
          <DetailItem
            label="superseded by"
            value={run.superseded_by_runtrace_ref}
            className="border-rose-100 bg-rose-50/80"
          />
          <DetailItem label="reason" value={run.interruption_reason} />
          <DetailItem label="dispatch" value={formatInlineList(run.interruption_dispatch_targets)} />
        </DetailBlock>
      </div>
      <DetailBlock title="Visible Handoff">
        <DetailItem label="source" value={run.latest_handoff_source_agent} />
        <DetailItem label="targets" value={formatInlineList(run.latest_handoff_targets)} />
        <DetailItem label="spoken" value={formatInlineList(run.spoken_bot_ids)} />
        <DetailItem label="remaining" value={formatInlineList(run.remaining_bot_ids)} />
      </DetailBlock>
    </div>
  )
}

function SessionSummary({ session }: { session: OpenClawSessionDetail }) {
  const transcript = session.transcript || []

  return (
    <div className="space-y-3">
      <div className="grid gap-3 md:grid-cols-2">
        <DetailBlock title="Session Signals">
          <DetailItem label="active run" value={session.active_runtrace_ref} />
          <DetailItem label="delivery guard epoch" value={session.delivery_guard_epoch ?? 0} />
          <DetailItem label="superseded runs" value={formatInlineList(session.superseded_runtrace_refs)} />
          <DetailItem label="recent strategies" value={formatInlineList(session.recent_run_strategies)} />
        </DetailBlock>
        <DetailBlock title="Working State">
          <DetailItem label="pending handoff" value={summarizePendingHandoff(session.pending_handoff)} />
          <DetailItem label="last committed state" value={compactJson(session.last_committed_state)} />
        </DetailBlock>
      </div>
      <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold text-slate-900">Transcript Signals</p>
          <span className="text-xs text-slate-400">{session.transcript_count ?? transcript.length} entries</span>
        </div>
        <div className="mt-3 space-y-3">
          {transcript.length ? (
            transcript.map((entry, index) => (
              <TranscriptSignalItem key={`${entry.actor}-${entry.created_at}-${index}`} entry={entry} />
            ))
          ) : (
            <p className="rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
              当前没有 transcript。
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export function OpenClawRuntimePage() {
  const {
    collections,
    details,
    selection,
    openControlUi,
    refreshAll,
    selectOpenClawRun,
    selectOpenClawSession,
  } = useDashboard()
  const [sessionSearch, setSessionSearch] = useState("")
  const [runSearch, setRunSearch] = useState("")
  const [activeTab, setActiveTab] = useState("sessions")

  const sessionColumns = useMemo<ColumnDef<OpenClawSessionView>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Session",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.title}</div>
            <div className="text-xs text-slate-500">{row.original.channel_id}</div>
            <div className="text-xs text-slate-400">
              active {row.original.active_runtrace_ref || "n/a"} · guard {row.original.delivery_guard_epoch ?? 0}
            </div>
            {row.original.pending_handoff_summary ? (
              <div className="text-xs text-amber-700">{row.original.pending_handoff_summary}</div>
            ) : null}
          </div>
        ),
      },
      {
        accessorKey: "surface",
        header: "Surface",
        cell: ({ row }) => <StatusBadge value={row.original.surface} />,
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge value={row.original.status} />,
      },
    ],
    []
  )

  const runColumns = useMemo<ColumnDef<OpenClawRunView>[]>(
    () => [
      {
        accessorKey: "work_ticket_ref",
        header: "Work Ticket",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.work_ticket_ref}</div>
            <div className="text-xs text-slate-500">{row.original.model_ref}</div>
            <div className="text-xs text-slate-400">{row.original.runtrace_id}</div>
          </div>
        ),
      },
      {
        accessorKey: "status",
        header: "Signals",
        cell: ({ row }) => (
          <div className="space-y-1 text-xs">
            <div className="flex flex-wrap gap-2">
              <StatusBadge value={row.original.status} />
              <StatusBadge value={row.original.strategy} />
            </div>
            <div className="text-slate-500">
              turns {row.original.visible_turn_count ?? 0} · guard {row.original.delivery_guard_epoch ?? 0}
            </div>
            {row.original.superseded_by_runtrace_ref ? (
              <div className="font-medium text-rose-600">superseded by {row.original.superseded_by_runtrace_ref}</div>
            ) : null}
            {row.original.supersedes_runtrace_ref ? (
              <div className="font-medium text-amber-700">supersedes {row.original.supersedes_runtrace_ref}</div>
            ) : null}
          </div>
        ),
      },
      {
        accessorKey: "last_event_at",
        header: "At",
        cell: ({ row }) => <span className="text-xs text-slate-500">{formatDateTime(row.original.last_event_at)}</span>,
      },
    ],
    []
  )

  const handoffColumns = useMemo<ColumnDef<OpenClawRunView>[]>(
    () => [
      {
        accessorKey: "latest_handoff_source_agent",
        header: "Source",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.latest_handoff_source_agent || "n/a"}</div>
            <div className="text-xs text-slate-500">{row.original.work_ticket_ref}</div>
          </div>
        ),
      },
      {
        accessorKey: "latest_handoff_targets",
        header: "Targets",
        cell: ({ row }) => (
          <div className="space-y-1 text-xs">
            <div className="text-slate-500">{formatInlineList(row.original.latest_handoff_targets)}</div>
            <div className="text-slate-400">{row.original.handoff_origin || "origin:n/a"}</div>
            <div className="text-slate-400">{row.original.handoff_resolution_basis || "basis:n/a"}</div>
            {row.original.collaboration_intent ? (
              <div className="text-slate-400">intent: {row.original.collaboration_intent}</div>
            ) : null}
            {!!row.original.reply_visible_named_targets?.length && (
              <div className="text-emerald-600">visible name: {row.original.reply_visible_named_targets.join(", ")}</div>
            )}
            {!!row.original.reply_name_targets?.length && (
              <div className="text-slate-400">reply name: {row.original.reply_name_targets.join(", ")}</div>
            )}
            {!!row.original.reply_semantic_handoff_targets?.length && (
              <div className="text-sky-600">reply semantic: {row.original.reply_semantic_handoff_targets.join(", ")}</div>
            )}
            {!!row.original.spoken_bot_ids?.length && (
              <div className="text-slate-400">spoken: {row.original.spoken_bot_ids.join(", ")}</div>
            )}
            {!!row.original.remaining_bot_ids?.length && (
              <div className="text-slate-400">remaining: {row.original.remaining_bot_ids.join(", ")}</div>
            )}
            {row.original.stop_reason ? <div className="font-medium text-slate-500">stop: {row.original.stop_reason}</div> : null}
            {row.original.handoff_contract_violation ? <div className="font-medium text-amber-600">contract violation</div> : null}
            {row.original.handoff_repetition_violation ? <div className="font-medium text-orange-600">repetition retry</div> : null}
            {row.original.stopped_by_turn_limit ? <div className="font-medium text-rose-600">stopped by limit</div> : null}
          </div>
        ),
      },
      {
        accessorKey: "handoff_count",
        header: "Turns",
        cell: ({ row }) => (
          <div className="space-y-1 text-xs">
            <StatusBadge value={`x${row.original.handoff_count || 0}`} />
            <div className="text-slate-400">visible {row.original.visible_turn_count ?? 0}</div>
            <div className="text-slate-400">budget {row.original.remaining_turn_budget ?? 0}</div>
          </div>
        ),
      },
    ],
    []
  )

  const bindingColumns = useMemo<ColumnDef<OpenClawAgentBinding>[]>(
    () => [
      {
        accessorKey: "employee_id",
        header: "Employee",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.employee_id}</div>
            <div className="text-xs text-slate-500">{row.original.openclaw_agent_id}</div>
          </div>
        ),
      },
      { accessorKey: "tool_profile", header: "Tool Profile" },
      { accessorKey: "sandbox_profile", header: "Sandbox" },
    ],
    []
  )

  const workspaceColumns = useMemo<ColumnDef<OpenClawWorkspaceBundle>[]>(
    () => [
      { accessorKey: "employee_id", header: "Employee" },
      { accessorKey: "bootstrap_entrypoint", header: "Entrypoint" },
      {
        accessorKey: "workspace_path",
        header: "Workspace",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.workspace_path}</code>,
      },
    ],
    []
  )

  const filteredSessions = collections.openclawSessions.filter((session) =>
    [
      session.thread_id,
      session.title,
      session.channel_id,
      session.work_ticket_ref || "",
      session.active_runtrace_ref || "",
      session.pending_handoff_summary || "",
      Object.values(session.openclaw_session_refs || {}).join(" "),
    ]
      .join(" ")
      .toLowerCase()
      .includes(sessionSearch.toLowerCase())
  )
  const filteredRuns = collections.openclawRecentRuns.filter((run) =>
    [
      run.runtrace_id,
      run.work_ticket_ref,
      run.thread_ref || "",
      run.model_ref,
      run.strategy,
      run.interaction_mode,
      run.supersedes_runtrace_ref || "",
      run.superseded_by_runtrace_ref || "",
      (run.interruption_dispatch_targets || []).join(" "),
    ]
      .join(" ")
      .toLowerCase()
      .includes(runSearch.toLowerCase())
  )
  const filteredVisibleHandoffs = filteredRuns.filter((run) => (run.handoff_count || 0) > 0)

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">OpenClaw Runtime</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Gateway、Session、Native Runs 与原生 hooks</h1>
        <p className="text-slate-600">运行态视图强调对 session / native run 的可读性，便于确认当前确实走在 OpenClaw 原生执行路径上。</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Gateway</CardDescription>
            <CardTitle className="flex items-center justify-between gap-3">
              <span>{collections.openclawGatewayHealth?.status || "unknown"}</span>
              <StatusBadge value={collections.openclawGatewayHealth?.status} />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>reachable: {String(collections.openclawGatewayHealth?.reachable ?? false)}</p>
            <p>sessions: {collections.openclawGatewayHealth?.active_session_refs || 0}</p>
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Runtime Mode</CardDescription>
            <CardTitle>{collections.openclawRuntimeMode?.runtime_mode || "compat"}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>{collections.openclawRuntimeMode?.gateway_base_url || "n/a"}</p>
            <p>{collections.openclawRuntimeMode?.runtime_home || "n/a"}</p>
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Hooks</CardDescription>
            <CardTitle>{collections.openclawHooks?.entries.length || 0} entries</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {(collections.openclawHooks?.entries || []).slice(0, 3).map((entry) => (
              <div key={entry.hook_id} className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-2 text-sm">
                <span className="font-medium text-slate-700">{entry.hook_id}</span>
                <StatusBadge value={entry.enabled ? "enabled" : "disabled"} />
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Visible Handoffs</CardDescription>
            <CardTitle>{collections.openclawRecentRuns.filter((run) => (run.handoff_count || 0) > 0).length} runs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-slate-600">
            <p>最近接棒链路都保持在可见 thread 内。</p>
            <p>无隐藏 DM，无额外 room。</p>
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Quick Actions</CardDescription>
            <CardTitle>Runtime Tools</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={openControlUi}>
              <LifeBuoy className="h-4 w-4" />
              Open Ready Control UI
            </Button>
            <Button variant="outline" onClick={() => void refreshAll()}>
              <RefreshCcw className="h-4 w-4" />
              Refresh Runtime
            </Button>
          </CardContent>
        </Card>
      </div>

      <ResizablePanelGroup direction="horizontal" className="min-h-[820px] overflow-hidden rounded-[28px] border border-white/80 bg-white/50 shadow-panel">
        <ResizablePanel defaultSize={60}>
          <div className="h-full p-4">
            <Card className="glass-panel h-full">
              <CardHeader>
                <CardDescription>Session / Native Run / Config Objects</CardDescription>
                <CardTitle>OpenClaw Runtime Browser</CardTitle>
              </CardHeader>
              <CardContent className="h-[calc(100%-5rem)]">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
                  <TabsList className="grid grid-cols-6">
                    <TabsTrigger value="sessions">Sessions</TabsTrigger>
                    <TabsTrigger value="runs">Native Runs</TabsTrigger>
                    <TabsTrigger value="handoffs">Visible Handoffs</TabsTrigger>
                    <TabsTrigger value="issues">Issues</TabsTrigger>
                    <TabsTrigger value="bindings">Bindings</TabsTrigger>
                    <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
                  </TabsList>

                  <div className="mt-4 h-[calc(100%-3rem)]">
                    <TabsContent value="sessions" className="space-y-4">
                      <Input placeholder="搜索 thread / channel / ticket" value={sessionSearch} onChange={(event) => setSessionSearch(event.target.value)} />
                      <DataTable
                        columns={sessionColumns}
                        data={filteredSessions}
                        getRowId={(row) => row.thread_id}
                        selectedRowId={selection.selectedOpenClawThreadId}
                        onRowClick={(row) => void selectOpenClawSession(row.thread_id)}
                        emptyMessage="当前还没有挂接 OpenClaw session 的线程"
                      />
                    </TabsContent>
                    <TabsContent value="runs" className="space-y-4">
                      <Input placeholder="搜索 runtrace / model / strategy" value={runSearch} onChange={(event) => setRunSearch(event.target.value)} />
                      <DataTable
                        columns={runColumns}
                        data={filteredRuns}
                        getRowId={(row) => row.runtrace_id}
                        selectedRowId={selection.selectedOpenClawRunId}
                        onRowClick={(row) => void selectOpenClawRun(row.runtrace_id)}
                        emptyMessage="最近还没有 native gateway run"
                      />
                    </TabsContent>
                    <TabsContent value="handoffs" className="space-y-4">
                      <Input placeholder="搜索 source / target / ticket" value={runSearch} onChange={(event) => setRunSearch(event.target.value)} />
                      <DataTable
                        columns={handoffColumns}
                        data={filteredVisibleHandoffs}
                        getRowId={(row) => row.runtrace_id}
                        selectedRowId={selection.selectedOpenClawRunId}
                        onRowClick={(row) => void selectOpenClawRun(row.runtrace_id)}
                        emptyMessage="最近还没有可见 bot handoff"
                      />
                    </TabsContent>
                    <TabsContent value="issues">
                      <JsonView value={collections.openclawIssues} empty="当前没有新的运行态问题。" />
                    </TabsContent>
                    <TabsContent value="bindings">
                      <DataTable columns={bindingColumns} data={collections.openclawBindings} getRowId={(row) => row.employee_id} emptyMessage="当前没有 OpenClaw agent binding" />
                    </TabsContent>
                    <TabsContent value="workspaces">
                      <DataTable columns={workspaceColumns} data={collections.openclawWorkspaceBundles} getRowId={(row) => row.employee_id} emptyMessage="当前没有 workspace bundle" />
                    </TabsContent>
                  </div>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={40}>
          <div className="h-full border-l border-white/80 bg-white/90 p-4">
            <Card className="glass-panel h-full">
              <CardHeader>
                <CardDescription>Runtime Inspector</CardDescription>
                <CardTitle>{activeTab === "runs" || activeTab === "handoffs" ? "Selected Native Run Detail" : "Selected Session Detail"}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {activeTab === "runs" || activeTab === "handoffs" ? (
                  details.openclawRunDetail ? (
                    <>
                      <div className="rounded-2xl border border-slate-200 bg-white p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="font-medium text-slate-950">{details.openclawRunDetail.work_ticket_ref}</p>
                            <p className="mt-1 text-sm text-slate-500">{details.openclawRunDetail.model_ref}</p>
                            <p className="mt-1 text-xs text-slate-400">
                              turn mode: {details.openclawRunDetail.latest_turn_mode || "source"} · remaining budget:{" "}
                              {details.openclawRunDetail.remaining_turn_budget ?? 0}
                            </p>
                          </div>
                          <StatusBadge value={details.openclawRunDetail.strategy} />
                        </div>
                      </div>
                      <RunSummary run={details.openclawRunDetail} />
                      <JsonView value={details.openclawRunDetail} />
                    </>
                  ) : (
                    <JsonView value={null} empty="选择一个 native run 查看详情。" />
                  )
                ) : details.openclawSessionDetail ? (
                  <>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-slate-950">{details.openclawSessionDetail.title}</p>
                          <p className="mt-1 text-sm text-slate-500">{details.openclawSessionDetail.channel_id}</p>
                        </div>
                        <StatusBadge value={details.openclawSessionDetail.surface} />
                      </div>
                    </div>
                    <SessionSummary session={details.openclawSessionDetail} />
                    <JsonView value={details.openclawSessionDetail} />
                  </>
                ) : (
                  <JsonView value={null} empty="选择一个 session 查看详情。" />
                )}
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
