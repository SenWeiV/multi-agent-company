import { useMemo } from "react"
import { type ColumnDef } from "@tanstack/react-table"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { DataTable } from "@/components/shared/data-table"
import { JsonView } from "@/components/shared/json-view"
import { StatusBadge } from "@/components/shared/status-badge"
import { useDashboard } from "@/context/dashboard-context"
import { formatDateTime } from "@/lib/utils"
import type { ConversationThread, MemoryNamespace } from "@/types/dashboard"

export function ConversationsPage() {
  const { collections, details, selection, selectThread } = useDashboard()

  const threadColumns = useMemo<ColumnDef<ConversationThread>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Thread",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.title}</div>
            <div className="text-xs text-slate-500">{row.original.surface}</div>
          </div>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge value={row.original.status} />,
      },
      {
        accessorKey: "channel_id",
        header: "Channel",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.channel_id}</code>,
      },
    ],
    []
  )

  const namespaceColumns = useMemo<ColumnDef<MemoryNamespace>[]>(
    () => [
      {
        accessorKey: "scope",
        header: "Scope",
        cell: ({ row }) => <div className="font-medium text-slate-950">{row.original.scope}</div>,
      },
      {
        accessorKey: "namespace_id",
        header: "Namespace",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.namespace_id}</code>,
      },
    ],
    []
  )

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">Conversations</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">线程、命名空间与上下文镜像</h1>
        <p className="text-slate-600">这里查看各交互表面的 ConversationThread，以及与 Memory Fabric 的 namespace 结构。</p>
      </div>

      <ResizablePanelGroup direction="horizontal" className="min-h-[760px] overflow-hidden rounded-[28px] border border-white/80 bg-white/50 shadow-panel">
        <ResizablePanel defaultSize={58}>
          <div className="grid h-full gap-4 p-4 lg:grid-cols-[1.2fr,0.8fr]">
            <Card className="glass-panel">
              <CardHeader>
                <CardDescription>Conversation Threads</CardDescription>
                <CardTitle>Threads</CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={threadColumns}
                  data={[...collections.threads].reverse()}
                  getRowId={(row) => row.thread_id}
                  selectedRowId={selection.selectedThreadId}
                  onRowClick={(row) => void selectThread(row.thread_id)}
                  emptyMessage="暂无 ConversationThread"
                />
              </CardContent>
            </Card>

            <Card className="glass-panel">
              <CardHeader>
                <CardDescription>Memory Fabric</CardDescription>
                <CardTitle>Namespaces</CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={namespaceColumns}
                  data={collections.namespaces}
                  getRowId={(row) => row.namespace_id}
                  emptyMessage="暂无 MemoryNamespace"
                />
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={42}>
          <div className="h-full border-l border-white/80 bg-white/90 p-4">
            <Card className="glass-panel h-full">
              <CardHeader>
                <CardDescription>Thread Inspector</CardDescription>
                <CardTitle>Selected Conversation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {details.selectedThreadDetail ? (
                  <>
                    <div className="grid gap-3 md:grid-cols-2">
                      <Card className="subtle-outline">
                        <CardContent className="space-y-2 p-4">
                          <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">Meta</p>
                          <div className="space-y-2 text-sm text-slate-600">
                            <div className="flex items-center justify-between gap-3">
                              <span>Thread</span>
                              <code>{details.selectedThreadDetail.thread_id}</code>
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <span>Surface</span>
                              <StatusBadge value={details.selectedThreadDetail.surface} />
                            </div>
                            <div className="flex items-center justify-between gap-3">
                              <span>Status</span>
                              <StatusBadge value={details.selectedThreadDetail.status} />
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                      <Card className="subtle-outline">
                        <CardContent className="space-y-2 p-4">
                          <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-500">Participants</p>
                          <div className="space-y-2 text-sm text-slate-600">
                            {(details.selectedThreadDetail.participant_ids || []).map((participant) => (
                              <div key={participant} className="rounded-xl bg-slate-100 px-3 py-2">
                                {participant}
                              </div>
                            ))}
                          </div>
                        </CardContent>
                      </Card>
                    </div>

                    {details.selectedThreadDetail.transcript?.length ? (
                      <div className="space-y-3">
                        {details.selectedThreadDetail.transcript.map((entry, index) => (
                          <Card key={`${entry.actor}-${index}`} className="subtle-outline">
                            <CardContent className="space-y-2 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium text-slate-950">{entry.actor}</p>
                                <span className="text-xs text-slate-500">{formatDateTime(entry.created_at)}</span>
                              </div>
                              <p className="text-sm leading-6 text-slate-600">{entry.text}</p>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    ) : (
                      <JsonView value={details.selectedThreadDetail} empty="该线程暂无可见 transcript。" />
                    )}
                  </>
                ) : (
                  <JsonView value={null} empty="选择一个 Thread 查看详情。" />
                )}
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
