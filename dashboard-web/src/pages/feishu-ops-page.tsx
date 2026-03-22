import { useMemo, useState } from "react"
import { type ColumnDef } from "@tanstack/react-table"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { DataTable } from "@/components/shared/data-table"
import { JsonView } from "@/components/shared/json-view"
import { StatusBadge } from "@/components/shared/status-badge"
import { useDashboard } from "@/context/dashboard-context"
import { formatDateTime, parseCommaList } from "@/lib/utils"
import type { FeishuBotApp, FeishuOutboundMessage, FeishuInboundEvent, ChannelBinding, FeishuGroupDebugEvent } from "@/types/dashboard"

export function FeishuOpsPage() {
  const {
    collections,
    details,
    selection,
    selectDeadLetter,
    replayDeadLetter,
    sendFeishuTest,
  } = useDashboard()
  const [deadLetterSearch, setDeadLetterSearch] = useState("")
  const [replaySearch, setReplaySearch] = useState("")
  const [groupDebugSearch, setGroupDebugSearch] = useState("")
  const [selectedGroupDebugId, setSelectedGroupDebugId] = useState<string | null>(null)
  const [sendAppId, setSendAppId] = useState("")
  const [sendChatId, setSendChatId] = useState("")
  const [sendText, setSendText] = useState("")
  const [sendMentions, setSendMentions] = useState("")

  const deadLetterColumns = useMemo<ColumnDef<FeishuOutboundMessage>[]>(
    () => [
      {
        accessorKey: "source_kind",
        header: "Source",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.source_kind}</div>
            <div className="line-clamp-2 text-xs text-slate-500">{row.original.text}</div>
          </div>
        ),
      },
      {
        accessorKey: "receive_id",
        header: "Chat",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.receive_id}</code>,
      },
      {
        accessorKey: "attempt_count",
        header: "Attempts",
        cell: ({ row }) => (
          <div className="space-y-1">
            <StatusBadge value={row.original.status} />
            <div className="text-xs text-slate-500">x {row.original.attempt_count || 1}</div>
          </div>
        ),
      },
    ],
    []
  )

  const replayColumns = useMemo<ColumnDef<FeishuOutboundMessage>[]>(
    () => [
      {
        accessorKey: "outbound_id",
        header: "Replay",
        cell: ({ row }) => (
          <div className="space-y-1">
            <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.outbound_id}</code>
            <div className="text-xs text-slate-500">{row.original.replay_source_outbound_ref || "root"}</div>
          </div>
        ),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge value={row.original.status} />,
      },
      {
        accessorKey: "created_at",
        header: "At",
        cell: ({ row }) => <span className="text-xs text-slate-500">{formatDateTime(row.original.created_at)}</span>,
      },
    ],
    []
  )

  const inboundColumns = useMemo<ColumnDef<FeishuInboundEvent>[]>(
    () => [
      { accessorKey: "surface", header: "Surface" },
      {
        accessorKey: "chat_id",
        header: "Chat",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.chat_id}</code>,
      },
      { accessorKey: "app_id", header: "App" },
    ],
    []
  )

  const outboundColumns = useMemo<ColumnDef<FeishuOutboundMessage>[]>(
    () => [
      {
        accessorKey: "source_kind",
        header: "Source",
        cell: ({ row }) => <div className="font-medium text-slate-950">{row.original.source_kind}</div>,
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusBadge value={row.original.status} />,
      },
      {
        accessorKey: "receive_id",
        header: "Chat",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.receive_id}</code>,
      },
    ],
    []
  )

  const botColumns = useMemo<ColumnDef<FeishuBotApp>[]>(
    () => [
      {
        accessorKey: "display_name",
        header: "Bot",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.display_name || row.original.employee_id}</div>
            <div className="text-xs text-slate-500">{row.original.employee_id}</div>
          </div>
        ),
      },
      {
        accessorKey: "app_id",
        header: "App",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.app_id}</code>,
      },
      {
        accessorKey: "bot_open_id",
        header: "Open ID",
        cell: ({ row }) => <span className="text-xs text-slate-500">{row.original.bot_open_id || "n/a"}</span>,
      },
    ],
    []
  )

  const bindingColumns = useMemo<ColumnDef<ChannelBinding>[]>(
    () => [
      { accessorKey: "surface", header: "Surface" },
      {
        accessorKey: "default_route",
        header: "Route",
        cell: ({ row }) => <code className="rounded bg-slate-100 px-2 py-1 text-xs">{row.original.default_route}</code>,
      },
      {
        accessorKey: "mention_policy",
        header: "Mention",
        cell: ({ row }) => <StatusBadge value={row.original.mention_policy} />,
      },
    ],
    []
  )

  const groupDebugColumns = useMemo<ColumnDef<FeishuGroupDebugEvent>[]>(
    () => [
      {
        accessorKey: "processed_status",
        header: "Status",
        cell: ({ row }) => <StatusBadge value={row.original.processed_status} />,
      },
      {
        accessorKey: "dispatch_mode",
        header: "Dispatch",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.dispatch_mode || "n/a"}</div>
            <div className="line-clamp-2 text-xs text-slate-500">
              {[
                row.original.match_basis,
                row.original.dispatch_resolution_basis,
                row.original.collaboration_intent,
                row.original.target_resolution_basis,
                row.original.text || "无文本",
              ]
                .filter(Boolean)
                .join(" · ")}
            </div>
          </div>
        ),
      },
      {
        accessorKey: "target_agent_ids",
        header: "Targets",
        cell: ({ row }) => (
          <div className="text-xs text-slate-500">
            {(row.original.target_agent_ids || []).length ? row.original.target_agent_ids?.join(", ") : "none"}
            {!!row.original.dispatch_targets?.length && (
              <div className="mt-1 text-[11px] text-slate-400">dispatch: {row.original.dispatch_targets.join(", ")}</div>
            )}
            {!!row.original.deterministic_name_target_ids?.length && (
              <div className="mt-1 text-[11px] text-slate-400">name: {row.original.deterministic_name_target_ids.join(", ")}</div>
            )}
            {!!row.original.semantic_dispatch_target_ids?.length && (
              <div className="mt-1 text-[11px] text-indigo-600">semantic: {row.original.semantic_dispatch_target_ids.join(", ")}</div>
            )}
            {!!row.original.deterministic_text_target_ids?.length && (
              <div className="mt-1 text-[11px] text-slate-400">text: {row.original.deterministic_text_target_ids.join(", ")}</div>
            )}
            {!!row.original.semantic_handoff_target_ids?.length && (
              <div className="mt-1 text-[11px] text-sky-600">llm: {row.original.semantic_handoff_target_ids.join(", ")}</div>
            )}
            {row.original.collaboration_intent ? (
              <div className="mt-1 text-[11px] text-slate-400">intent: {row.original.collaboration_intent}</div>
            ) : null}
          </div>
        ),
      },
    ],
    []
  )

  const filteredDeadLetters = collections.feishuDeadLetters.filter((item) =>
    [item.outbound_id, item.receive_id, item.text, item.error_detail || "", item.work_ticket_ref || ""]
      .join(" ")
      .toLowerCase()
      .includes(deadLetterSearch.toLowerCase())
  )
  const filteredReplayAudit = collections.feishuReplayAudit.filter((item) =>
    [
      item.outbound_id,
      item.replay_source_outbound_ref || "",
      item.replay_root_outbound_ref || "",
      item.receive_id,
      item.work_ticket_ref || "",
      item.thread_ref || "",
      item.runtrace_ref || "",
    ]
      .join(" ")
      .toLowerCase()
      .includes(replaySearch.toLowerCase())
  )
  const filteredGroupDebug = collections.feishuGroupDebug.filter((item) =>
    [
      item.debug_event_id,
      item.chat_id,
      item.text || "",
      item.dispatch_mode || "",
      item.match_basis || "",
      item.dispatch_resolution_basis || "",
      item.collaboration_intent || "",
      item.target_resolution_basis || "",
      item.processed_status,
      (item.raw_mentions_summary || []).join(" "),
      (item.dispatch_targets || []).join(" "),
      (item.deterministic_name_target_ids || []).join(" "),
      (item.semantic_dispatch_target_ids || []).join(" "),
      (item.target_agent_ids || []).join(" "),
      (item.deterministic_text_target_ids || []).join(" "),
      (item.semantic_handoff_target_ids || []).join(" "),
    ]
      .join(" ")
      .toLowerCase()
      .includes(groupDebugSearch.toLowerCase())
  )
  const selectedGroupDebug =
    filteredGroupDebug.find((item) => item.debug_event_id === selectedGroupDebugId) || filteredGroupDebug[0] || null

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">Feishu Ops</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">机器人、通道、收发事件与 dead-letter 重放</h1>
        <p className="text-slate-600">这里保留了旧控制台的 dead-letter、replay audit 和 test send 能力，但改成更适合运营排查的多视图布局。</p>
      </div>

      <ResizablePanelGroup direction="horizontal" className="min-h-[820px] overflow-hidden rounded-[28px] border border-white/80 bg-white/50 shadow-panel">
        <ResizablePanel defaultSize={62}>
          <div className="h-full space-y-4 p-4">
            <div className="grid gap-4 md:grid-cols-5">
              <Card className="glass-panel"><CardContent className="p-5"><p className="text-sm text-slate-500">Bots</p><p className="mt-2 text-3xl font-semibold">{collections.feishuBots.length}</p></CardContent></Card>
              <Card className="glass-panel"><CardContent className="p-5"><p className="text-sm text-slate-500">Inbound</p><p className="mt-2 text-3xl font-semibold">{collections.feishuInbound.length}</p></CardContent></Card>
              <Card className="glass-panel"><CardContent className="p-5"><p className="text-sm text-slate-500">Group Debug</p><p className="mt-2 text-3xl font-semibold">{collections.feishuGroupDebug.length}</p></CardContent></Card>
              <Card className="glass-panel"><CardContent className="p-5"><p className="text-sm text-slate-500">Outbound</p><p className="mt-2 text-3xl font-semibold">{collections.feishuOutbound.length}</p></CardContent></Card>
              <Card className="glass-panel"><CardContent className="p-5"><p className="text-sm text-slate-500">Dead Letters</p><p className="mt-2 text-3xl font-semibold">{collections.feishuDeadLetters.length}</p></CardContent></Card>
            </div>

            <Card className="glass-panel h-[calc(100%-7rem)]">
              <CardHeader>
                <CardDescription>Error Queue + Event Streams</CardDescription>
                <CardTitle>Feishu Operating Views</CardTitle>
              </CardHeader>
              <CardContent className="h-[calc(100%-5rem)]">
                <Tabs defaultValue="dead-letters" className="h-full">
                  <TabsList className="grid grid-cols-7">
                    <TabsTrigger value="dead-letters">Dead Letters</TabsTrigger>
                    <TabsTrigger value="replay-audit">Replay Audit</TabsTrigger>
                    <TabsTrigger value="group-debug">Group Debug</TabsTrigger>
                    <TabsTrigger value="inbound">Inbound</TabsTrigger>
                    <TabsTrigger value="outbound">Outbound</TabsTrigger>
                    <TabsTrigger value="bots">Bots</TabsTrigger>
                    <TabsTrigger value="bindings">Bindings</TabsTrigger>
                  </TabsList>
                  <div className="mt-4 h-[calc(100%-3rem)]">
                    <TabsContent value="dead-letters" className="space-y-4">
                      <Input placeholder="搜索 outbound/chat/text" value={deadLetterSearch} onChange={(event) => setDeadLetterSearch(event.target.value)} />
                      <DataTable
                        columns={deadLetterColumns}
                        data={filteredDeadLetters}
                        selectedRowId={selection.selectedDeadLetterId}
                        getRowId={(row) => row.outbound_id}
                        onRowClick={(row) => void selectDeadLetter(row.outbound_id)}
                        emptyMessage="当前没有 dead letter"
                      />
                    </TabsContent>
                    <TabsContent value="replay-audit" className="space-y-4">
                      <Input placeholder="搜索 replay ref / chat / ticket" value={replaySearch} onChange={(event) => setReplaySearch(event.target.value)} />
                      <DataTable
                        columns={replayColumns}
                        data={filteredReplayAudit}
                        getRowId={(row) => row.outbound_id}
                        emptyMessage="当前还没有 replay audit 记录"
                      />
                    </TabsContent>
                    <TabsContent value="group-debug" className="space-y-4">
                      <Input placeholder="搜索 group debug / mentions / targets" value={groupDebugSearch} onChange={(event) => setGroupDebugSearch(event.target.value)} />
                      <DataTable
                        columns={groupDebugColumns}
                        data={filteredGroupDebug}
                        getRowId={(row) => row.debug_event_id}
                        selectedRowId={selectedGroupDebug?.debug_event_id ?? null}
                        onRowClick={(row) => setSelectedGroupDebugId(row.debug_event_id)}
                        emptyMessage="还没有捕获到群聊提及样本"
                      />
                    </TabsContent>
                    <TabsContent value="inbound">
                      <DataTable columns={inboundColumns} data={[...collections.feishuInbound].reverse()} getRowId={(row) => `${row.app_id}-${row.chat_id}`} emptyMessage="最近没有 inbound 事件" />
                    </TabsContent>
                    <TabsContent value="outbound">
                      <DataTable columns={outboundColumns} data={[...collections.feishuOutbound].reverse()} getRowId={(row) => row.outbound_id} emptyMessage="最近没有 outbound 消息" />
                    </TabsContent>
                    <TabsContent value="bots">
                      <DataTable columns={botColumns} data={collections.feishuBots} getRowId={(row) => row.app_id} emptyMessage="当前没有 Feishu bot" />
                    </TabsContent>
                    <TabsContent value="bindings">
                      <DataTable
                        columns={bindingColumns}
                        data={collections.channelBindings.filter((binding) => binding.provider === "feishu")}
                        getRowId={(row) => row.binding_id}
                        emptyMessage="当前没有 Feishu channel binding"
                      />
                    </TabsContent>
                  </div>
                </Tabs>
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={38}>
          <div className="h-full space-y-4 border-l border-white/80 bg-white/90 p-4">
            <Card className="glass-panel">
              <CardHeader>
                <CardDescription>Dead Letter Inspector</CardDescription>
                <CardTitle>Selected Dead Letter</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {details.feishuDeadLetterDetail ? (
                  <>
                    <div className="rounded-2xl border border-rose-100 bg-rose-50/80 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-slate-950">{details.feishuDeadLetterDetail.dead_letter.source_kind}</p>
                          <p className="mt-1 line-clamp-3 text-sm text-slate-600">{details.feishuDeadLetterDetail.dead_letter.text}</p>
                        </div>
                        <StatusBadge value={details.feishuDeadLetterDetail.dead_letter.status} />
                      </div>
                      <p className="mt-3 text-xs text-rose-700">{details.feishuDeadLetterDetail.dead_letter.error_detail || "待处理"}</p>
                      <Button className="mt-4 w-full" onClick={() => void replayDeadLetter(details.feishuDeadLetterDetail!.dead_letter.outbound_id)}>
                        Replay Dead Letter
                      </Button>
                    </div>

                    <div className="space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Replay History</p>
                      {(details.feishuDeadLetterDetail.replay_history || []).length ? (
                        details.feishuDeadLetterDetail.replay_history.map((entry) => (
                          <article key={entry.outbound_id} className="rounded-2xl border border-slate-200 bg-white p-4">
                            <div className="flex items-center justify-between gap-3">
                              <code className="rounded bg-slate-100 px-2 py-1 text-xs">{entry.outbound_id}</code>
                              <StatusBadge value={entry.status} />
                            </div>
                            <p className="mt-2 text-xs text-slate-500">{formatDateTime(entry.created_at)}</p>
                          </article>
                        ))
                      ) : (
                        <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                          这个 dead letter 还没有 replay 历史。
                        </div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                    选择一个 dead letter 查看详情。
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="glass-panel">
              <CardHeader>
                <CardDescription>Feishu Group Debug</CardDescription>
                <CardTitle>Selected Group Debug Event</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {selectedGroupDebug ? (
                  <>
                    <div className="rounded-2xl border border-slate-200 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-slate-950">{selectedGroupDebug.dispatch_mode || "n/a"}</p>
                          <p className="mt-1 text-sm text-slate-500">{selectedGroupDebug.chat_id}</p>
                          <p className="mt-1 text-xs text-slate-400">Match basis: {selectedGroupDebug.match_basis || "n/a"}</p>
                        </div>
                        <StatusBadge value={selectedGroupDebug.processed_status} />
                      </div>
                      <p className="mt-3 text-sm text-slate-600">{selectedGroupDebug.text || "无文本内容"}</p>
                    </div>
                    <JsonView value={selectedGroupDebug} />
                  </>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
                    等下一条群聊样本进来后，这里会显示 mention 原始结构和命中结果。
                  </div>
                )}
              </CardContent>
            </Card>

            <Card className="glass-panel">
              <CardHeader>
                <CardDescription>Test Send</CardDescription>
                <CardTitle>发送一条飞书测试消息</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Select value={sendAppId} onValueChange={setSendAppId}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择 Bot App" />
                  </SelectTrigger>
                  <SelectContent>
                    {collections.feishuBots.map((bot) => (
                      <SelectItem key={bot.app_id} value={bot.app_id}>
                        {bot.display_name || bot.employee_id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input placeholder="Chat ID" value={sendChatId} onChange={(event) => setSendChatId(event.target.value)} />
                <Textarea rows={4} placeholder="发送一条测试消息" value={sendText} onChange={(event) => setSendText(event.target.value)} />
                <Input placeholder="Mention employee ids, comma separated" value={sendMentions} onChange={(event) => setSendMentions(event.target.value)} />
                <Button
                  className="w-full"
                  onClick={async () => {
                    await sendFeishuTest({
                      appId: sendAppId,
                      chatId: sendChatId,
                      text: sendText,
                      mentionEmployeeIds: parseCommaList(sendMentions),
                    })
                    setSendText("")
                    setSendMentions("")
                  }}
                >
                  Send Feishu Test
                </Button>
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
