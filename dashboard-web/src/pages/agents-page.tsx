import { useEffect, useMemo, useState } from "react"
import { type ColumnDef } from "@tanstack/react-table"
import { LifeBuoy, RefreshCcw, RotateCcw, Save } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ResizableHandle, ResizablePanel, ResizablePanelGroup } from "@/components/ui/resizable"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { DataTable } from "@/components/shared/data-table"
import { JsonView } from "@/components/shared/json-view"
import { StatusBadge } from "@/components/shared/status-badge"
import { useDashboard } from "@/context/dashboard-context"
import {
  fetchOpenClawAgentDetail,
  recheckOpenClawAgentSkills,
  syncOpenClawAgent,
  updateOpenClawWorkspaceFile,
} from "@/lib/api"
import { formatDateTime } from "@/lib/utils"
import type {
  EmployeePackSummary,
  OpenClawAgentDetail,
  OpenClawNativeSkill,
  OpenClawRunView,
  OpenClawSessionView,
} from "@/types/dashboard"

const EDITABLE_FILE_ORDER = ["BOOTSTRAP.md", "AGENTS.md", "IDENTITY.md", "SOUL.md", "SKILLS.md", "TOOLS.md", "HEARTBEAT.md", "USER.md"]

export function AgentsPage() {
  const {
    collections,
    openControlUi,
    refreshAll,
    syncOpenClawProvision,
    updateOpenClawBinding,
  } = useDashboard()
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null)
  const [detail, setDetail] = useState<OpenClawAgentDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [activeTab, setActiveTab] = useState("overview")
  const [filePath, setFilePath] = useState("BOOTSTRAP.md")
  const [fileDraft, setFileDraft] = useState("")
  const [skillSearch, setSkillSearch] = useState("")
  const [toolProfile, setToolProfile] = useState("")
  const [sandboxProfile, setSandboxProfile] = useState("")

  const selectedEmployee = useMemo(
    () => collections.employeePacks.find((item) => item.employee_id === selectedEmployeeId) || null,
    [collections.employeePacks, selectedEmployeeId]
  )

  useEffect(() => {
    if (!selectedEmployeeId && collections.employeePacks.length) {
      setSelectedEmployeeId(collections.employeePacks[0].employee_id)
    }
  }, [collections.employeePacks, selectedEmployeeId])

  useEffect(() => {
    if (!selectedEmployeeId) return
    let cancelled = false
    setLoadingDetail(true)
    void fetchOpenClawAgentDetail(selectedEmployeeId)
      .then((payload) => {
        if (cancelled) return
        setDetail(payload)
        setToolProfile(payload.binding.tool_profile)
        setSandboxProfile(payload.binding.sandbox_profile)
        const defaultFile = payload.workspace_files.find((file) => EDITABLE_FILE_ORDER.includes(file.path))?.path || "BOOTSTRAP.md"
        setFilePath(defaultFile)
        setFileDraft(payload.workspace_files.find((file) => file.path === defaultFile)?.content || "")
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false)
      })
    return () => {
      cancelled = true
    }
  }, [selectedEmployeeId])

  useEffect(() => {
    if (!detail) return
    const content = detail.workspace_files.find((file) => file.path === filePath)?.content || ""
    setFileDraft(content)
  }, [detail, filePath])

  const agentColumns = useMemo<ColumnDef<EmployeePackSummary>[]>(
    () => [
      {
        accessorKey: "employee_name",
        header: "Agent",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.employee_name}</div>
            <div className="text-xs text-slate-500">{row.original.employee_id}</div>
          </div>
        ),
      },
      {
        accessorKey: "department",
        header: "Department",
        cell: ({ row }) => <span className="text-sm text-slate-600">{row.original.department}</span>,
      },
      {
        accessorKey: "summary",
        header: "Summary",
        cell: ({ row }) => <span className="line-clamp-2 text-sm text-slate-500">{row.original.summary}</span>,
      },
    ],
    []
  )

  const skillColumns = useMemo<ColumnDef<OpenClawNativeSkill>[]>(
    () => [
      {
        accessorKey: "skill_name",
        header: "Skill",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.skill_name}</div>
            <div className="text-xs text-slate-500">{row.original.native_skill_name}</div>
          </div>
        ),
      },
      {
        accessorKey: "scope",
        header: "Scope",
        cell: ({ row }) => <StatusBadge value={row.original.scope} />,
      },
      {
        accessorKey: "verification_status",
        header: "Verify",
        cell: ({ row }) => (
          <div className="space-y-1">
            <StatusBadge value={row.original.verification_status} />
            <div className="text-[11px] text-slate-500">
              export={row.original.exported ? "yes" : "no"} / discovered={row.original.discovered ? "yes" : "no"}
            </div>
          </div>
        ),
      },
      {
        accessorKey: "source_ref.repo_name",
        header: "Source",
        cell: ({ row }) => (
          <div className="space-y-1 text-xs text-slate-500">
            <div>{row.original.source_ref.repo_name}</div>
            <div>{row.original.source_ref.path}</div>
            {row.original.discovery_detail ? <div>{row.original.discovery_detail}</div> : null}
          </div>
        ),
      },
    ],
    []
  )

  const sessionColumns = useMemo<ColumnDef<OpenClawSessionView>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Session",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.title}</div>
            <div className="text-xs text-slate-500">{row.original.channel_id}</div>
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
        header: "Run",
        cell: ({ row }) => (
          <div className="space-y-1">
            <div className="font-medium text-slate-950">{row.original.work_ticket_ref}</div>
            <div className="text-xs text-slate-500">{row.original.model_ref}</div>
          </div>
        ),
      },
      {
        accessorKey: "strategy",
        header: "Strategy",
        cell: ({ row }) => <StatusBadge value={row.original.strategy} />,
      },
      {
        accessorKey: "last_event_at",
        header: "At",
        cell: ({ row }) => <span className="text-xs text-slate-500">{formatDateTime(row.original.last_event_at)}</span>,
      },
    ],
    []
  )

  const filteredSkills = (detail?.native_skills || []).filter((skill) =>
    [skill.skill_name, skill.native_skill_name, skill.source_ref.repo_name, skill.source_ref.path]
      .join(" ")
      .toLowerCase()
      .includes(skillSearch.toLowerCase())
  )
  const editableFiles = (detail?.workspace_files || []).filter((file) => EDITABLE_FILE_ORDER.includes(file.path))

  const professionalSkillCount = detail?.native_skills.filter((skill) => skill.scope === "professional").length || 0
  const generalSkillCount = detail?.native_skills.filter((skill) => skill.scope === "general").length || 0
  const readySkillCount = detail?.native_skills.filter((skill) => skill.verification_status === "ready").length || 0
  const pendingSkillCount = detail?.native_skills.filter((skill) => skill.verification_status === "pending_sync").length || 0
  const invalidSkillCount = detail?.native_skills.filter((skill) => !["ready", "pending_sync"].includes(skill.verification_status)).length || 0

  async function reloadDetail() {
    if (!selectedEmployeeId) return
    const payload = await fetchOpenClawAgentDetail(selectedEmployeeId)
    setDetail(payload)
    setToolProfile(payload.binding.tool_profile)
    setSandboxProfile(payload.binding.sandbox_profile)
    setFileDraft(payload.workspace_files.find((file) => file.path === filePath)?.content || "")
  }

  async function saveWorkspaceFile() {
    if (!selectedEmployeeId) return
    await updateOpenClawWorkspaceFile(selectedEmployeeId, filePath, fileDraft)
    await refreshAll()
    await reloadDetail()
  }

  async function saveBinding() {
    if (!selectedEmployeeId) return
    await updateOpenClawBinding(selectedEmployeeId, {
      tool_profile: toolProfile,
      sandbox_profile: sandboxProfile,
    })
    await reloadDetail()
  }

  async function syncSelectedAgent() {
    if (!selectedEmployeeId) return
    const payload = await syncOpenClawAgent(selectedEmployeeId)
    setDetail(payload)
    setToolProfile(payload.binding.tool_profile)
    setSandboxProfile(payload.binding.sandbox_profile)
    await refreshAll()
  }

  async function recheckSelectedAgentSkills() {
    if (!selectedEmployeeId) return
    const payload = await recheckOpenClawAgentSkills(selectedEmployeeId)
    setDetail(payload)
    setToolProfile(payload.binding.tool_profile)
    setSandboxProfile(payload.binding.sandbox_profile)
    await refreshAll()
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">Agents</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">核心 7 席位的 OpenClaw 原生 Agent 管理台</h1>
        <p className="text-slate-600">统一查看 agent 基本信息、identity files、native skills、memory、runtime 和 OpenClaw 配置。</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Core 7</CardDescription>
            <CardTitle>{collections.employeePacks.length} agents</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            Dashboard 与 OpenClaw runtime 现在统一只保留 7 个核心席位。
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Native Skills</CardDescription>
            <CardTitle>{professionalSkillCount + generalSkillCount}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1 text-sm text-slate-600">
            <p>专业：{professionalSkillCount}</p>
            <p>通用：{generalSkillCount}</p>
            <p>ready：{readySkillCount}</p>
            <p>pending_sync：{pendingSkillCount}</p>
            <p>invalid：{invalidSkillCount}</p>
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Workspace</CardDescription>
            <CardTitle>{detail?.workspace_bundle.workspace_path || "n/a"}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-600">
            bootstrap、native skills 与 runtime bindings 都从这里同步到 OpenClaw。
          </CardContent>
        </Card>
        <Card className="glass-panel">
          <CardHeader className="pb-3">
            <CardDescription>Actions</CardDescription>
            <CardTitle>Sync / UI</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button variant="outline" onClick={() => void syncOpenClawProvision()}>
              <RefreshCcw className="h-4 w-4" />
              Provision Sync
            </Button>
            <Button variant="outline" onClick={() => void syncSelectedAgent()} disabled={!selectedEmployeeId}>
              <RefreshCcw className="h-4 w-4" />
              Agent Sync
            </Button>
            <Button variant="outline" onClick={() => void recheckSelectedAgentSkills()} disabled={!selectedEmployeeId}>
              <RotateCcw className="h-4 w-4" />
              Skills Recheck
            </Button>
            <Button onClick={openControlUi}>
              <LifeBuoy className="h-4 w-4" />
              Open Control UI
            </Button>
          </CardContent>
        </Card>
      </div>

      <ResizablePanelGroup direction="horizontal" className="min-h-[860px] overflow-hidden rounded-[28px] border border-white/80 bg-white/50 shadow-panel">
        <ResizablePanel defaultSize={34} minSize={26}>
          <div className="h-full p-4">
            <Card className="glass-panel h-full">
              <CardHeader>
                <CardDescription>Core Agents</CardDescription>
                <CardTitle>Agent Browser</CardTitle>
              </CardHeader>
              <CardContent>
                <DataTable
                  columns={agentColumns}
                  data={collections.employeePacks}
                  getRowId={(row) => row.employee_id}
                  selectedRowId={selectedEmployeeId}
                  onRowClick={(row) => setSelectedEmployeeId(row.employee_id)}
                  emptyMessage="暂无核心 agent"
                />
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={66} minSize={40}>
          <div className="h-full border-l border-white/80 bg-white/90 p-4">
            <Card className="glass-panel h-full">
              <CardHeader className="border-b border-slate-200">
                <CardDescription>Agent Detail</CardDescription>
                <CardTitle>
                  {selectedEmployee?.employee_name || "Select an agent"}
                  {loadingDetail ? " · loading..." : ""}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {detail ? (
                  <Tabs value={activeTab} onValueChange={setActiveTab} className="h-full">
                    <TabsList className="mx-4 mt-4 grid grid-cols-6">
                      <TabsTrigger value="overview">Overview</TabsTrigger>
                      <TabsTrigger value="identity">Identity</TabsTrigger>
                      <TabsTrigger value="skills">Native Skills</TabsTrigger>
                      <TabsTrigger value="memory">Memory</TabsTrigger>
                      <TabsTrigger value="runtime">Runtime</TabsTrigger>
                      <TabsTrigger value="config">Config</TabsTrigger>
                    </TabsList>

                    <div className="p-4">
                      <TabsContent value="overview" className="space-y-4">
                        <div className="grid gap-4 xl:grid-cols-2">
                          <Card>
                            <CardHeader>
                              <CardDescription>Basic</CardDescription>
                              <CardTitle>{detail.agent.employee_name}</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2 text-sm text-slate-600">
                              <p>employee_id: <code>{detail.agent.employee_id}</code></p>
                              <p>department: {detail.agent.department}</p>
                              <p>openclaw_agent_id: <code>{detail.agent.openclaw_agent_id}</code></p>
                              <p>model: <code>{detail.agent.primary_model_ref}</code></p>
                              <p>provider: {detail.agent.provider_name} / {detail.agent.model_name}</p>
                            </CardContent>
                          </Card>
                          <Card>
                            <CardHeader>
                              <CardDescription>Role Contract</CardDescription>
                              <CardTitle>Identity</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-3 text-sm text-slate-600">
                              <p>{detail.agent.identity_profile.identity}</p>
                              <div>
                                <p className="font-medium text-slate-950">Source Personas</p>
                                <p>{(detail.agent.source_persona_roles || []).join(" / ") || "n/a"}</p>
                              </div>
                              <div>
                                <p className="font-medium text-slate-950">Decision Lens</p>
                                <ul className="list-disc space-y-1 pl-5">
                                  {(detail.agent.identity_profile.decision_lens || []).slice(0, 5).map((item) => (
                                    <li key={item}>{item}</li>
                                  ))}
                                </ul>
                              </div>
                            </CardContent>
                          </Card>
                        </div>
                        <JsonView
                          value={{
                            workflow_hints: detail.agent.workflow_hints,
                            memory_instructions: detail.agent.memory_instructions,
                            role_boundaries: detail.agent.identity_profile.role_boundaries,
                            collaboration_rules: detail.agent.identity_profile.collaboration_rules,
                          }}
                        />
                      </TabsContent>

                      <TabsContent value="identity" className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-[280px,1fr]">
                          <Card>
                            <CardHeader>
                              <CardDescription>Workspace Files</CardDescription>
                              <CardTitle>Editable Docs</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                              {editableFiles.map((file) => (
                                <Button
                                  key={file.path}
                                  variant={file.path === filePath ? "default" : "outline"}
                                  className="w-full justify-start"
                                  onClick={() => setFilePath(file.path)}
                                >
                                  {file.path}
                                </Button>
                              ))}
                            </CardContent>
                          </Card>
                          <Card>
                            <CardHeader>
                              <CardDescription>{filePath}</CardDescription>
                              <CardTitle>Workspace Source Of Truth</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                              <Textarea rows={24} value={fileDraft} onChange={(event) => setFileDraft(event.target.value)} />
                              <div className="flex gap-3">
                                <Button onClick={() => void saveWorkspaceFile()}>
                                  <Save className="h-4 w-4" />
                                  Save File
                                </Button>
                                <Button variant="outline" onClick={() => setFileDraft(detail.workspace_files.find((file) => file.path === filePath)?.content || "")}>
                                  Reset Draft
                                </Button>
                              </div>
                            </CardContent>
                          </Card>
                        </div>
                      </TabsContent>

                      <TabsContent value="skills" className="space-y-4">
                        <Input placeholder="搜索 skill / repo / path" value={skillSearch} onChange={(event) => setSkillSearch(event.target.value)} />
                        <DataTable
                          columns={skillColumns}
                          data={filteredSkills}
                          getRowId={(row) => row.native_skill_name}
                          emptyMessage="当前没有 native skills"
                        />
                      </TabsContent>

                      <TabsContent value="memory" className="space-y-4">
                        <div className="grid gap-4 xl:grid-cols-2">
                          <Card>
                            <CardHeader>
                              <CardDescription>Namespaces</CardDescription>
                              <CardTitle>{detail.memory_namespaces.length}</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <JsonView value={detail.memory_namespaces} empty="当前没有 memory namespace" />
                            </CardContent>
                          </Card>
                          <Card>
                            <CardHeader>
                              <CardDescription>Recent Records</CardDescription>
                              <CardTitle>{detail.recent_memory_records.length}</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <JsonView value={detail.recent_memory_records} empty="当前没有 recent memory" />
                            </CardContent>
                          </Card>
                        </div>
                      </TabsContent>

                      <TabsContent value="runtime" className="space-y-4">
                        <div className="grid gap-4 xl:grid-cols-2">
                          <Card>
                            <CardHeader>
                              <CardDescription>Recent Sessions</CardDescription>
                              <CardTitle>{detail.recent_sessions.length}</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <DataTable
                                columns={sessionColumns}
                                data={detail.recent_sessions}
                                getRowId={(row) => row.thread_id}
                                emptyMessage="当前没有 recent sessions"
                              />
                            </CardContent>
                          </Card>
                          <Card>
                            <CardHeader>
                              <CardDescription>Recent Runs</CardDescription>
                              <CardTitle>{detail.recent_runs.length}</CardTitle>
                            </CardHeader>
                            <CardContent>
                              <DataTable
                                columns={runColumns}
                                data={detail.recent_runs}
                                getRowId={(row) => row.runtrace_id}
                                emptyMessage="当前没有 recent runs"
                              />
                            </CardContent>
                          </Card>
                        </div>
                      </TabsContent>

                      <TabsContent value="config" className="space-y-4">
                        <div className="grid gap-4 xl:grid-cols-2">
                          <Card>
                            <CardHeader>
                              <CardDescription>Binding</CardDescription>
                              <CardTitle>{detail.binding.openclaw_agent_id}</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                              <div className="space-y-2">
                                <span className="text-sm font-medium text-slate-600">Tool profile</span>
                                <Input value={toolProfile} onChange={(event) => setToolProfile(event.target.value)} />
                              </div>
                              <div className="space-y-2">
                                <span className="text-sm font-medium text-slate-600">Sandbox profile</span>
                                <Input value={sandboxProfile} onChange={(event) => setSandboxProfile(event.target.value)} />
                              </div>
                              <Button onClick={() => void saveBinding()}>
                                <Save className="h-4 w-4" />
                                Save Binding
                              </Button>
                            </CardContent>
                          </Card>
                          <Card>
                            <CardHeader>
                              <CardDescription>Workspace / Native Skills</CardDescription>
                              <CardTitle>Export State</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2 text-sm text-slate-600">
                              <p>workspace: <code>{detail.workspace_bundle.workspace_path}</code></p>
                              <p>agentDir: <code>{detail.binding.agent_dir || "n/a"}</code></p>
                              <p>bootstrap: <code>{detail.workspace_bundle.bootstrap_entrypoint}</code></p>
                              <p>channel accounts: {Object.keys(detail.binding.channel_accounts || {}).length}</p>
                              <p>native skill dirs: {detail.native_skills.length}</p>
                            </CardContent>
                          </Card>
                        </div>
                        <JsonView value={detail.binding} />
                      </TabsContent>
                    </div>
                  </Tabs>
                ) : (
                  <div className="p-8 text-sm text-slate-500">请选择一个核心 agent。</div>
                )}
              </CardContent>
            </Card>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
