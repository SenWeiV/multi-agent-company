import { useMemo } from "react"
import { Save } from "lucide-react"

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { useDashboard } from "@/context/dashboard-context"
import { parseCommaList } from "@/lib/utils"

export function SettingsPage() {
  const {
    collections,
    updateChannelBinding,
    updateRoomPolicy,
    updateOpenClawBinding,
    updateOpenClawHook,
    syncOpenClawProvision,
  } = useDashboard()

  const feishuBindings = useMemo(
    () => collections.channelBindings.filter((binding) => binding.provider === "feishu"),
    [collections.channelBindings]
  )
  const coreEmployeePacks = useMemo(
    () =>
      [...collections.employeePacks].sort((left, right) => left.department.localeCompare(right.department, "zh-CN")),
    [collections.employeePacks]
  )
  const validation = collections.skillCatalogValidation

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">Settings</p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-950">Feishu / OpenClaw 运行态配置编辑</h1>
        <p className="text-slate-600">密钥仍由后端环境变量托管，这里只编辑运行态策略和原生 OpenClaw 绑定、hook 配置。</p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="glass-panel">
          <CardHeader>
            <CardDescription>Visible Communication Orchestration</CardDescription>
            <CardTitle>Feishu Config Editor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Accordion type="multiple" className="space-y-4">
              {feishuBindings.map((binding) => (
                <AccordionItem key={binding.binding_id} value={binding.binding_id} className="rounded-2xl border border-slate-200 bg-white px-4">
                  <AccordionTrigger className="text-left">
                    <div>
                      <p className="font-medium text-slate-950">{binding.binding_id}</p>
                      <p className="text-xs text-slate-500">{binding.surface}</p>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <form
                      className="space-y-3"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        const data = new FormData(event.currentTarget)
                        await updateChannelBinding(binding.binding_id, {
                          default_route: String(data.get("default_route") || ""),
                          mention_policy: String(data.get("mention_policy") || ""),
                          sync_back_policy: String(data.get("sync_back_policy") || ""),
                          room_policy_ref: String(data.get("room_policy_ref") || "") || null,
                        })
                      }}
                    >
                      <Input name="default_route" defaultValue={binding.default_route} placeholder="default route" />
                      <Input name="mention_policy" defaultValue={binding.mention_policy} placeholder="mention policy" />
                      <Input name="sync_back_policy" defaultValue={binding.sync_back_policy} placeholder="sync back policy" />
                      <Input name="room_policy_ref" defaultValue={binding.room_policy_ref || ""} placeholder="room policy ref" />
                      <Button type="submit" className="w-full">
                        <Save className="h-4 w-4" />
                        Save Channel Binding
                      </Button>
                    </form>
                  </AccordionContent>
                </AccordionItem>
              ))}

              {collections.roomPolicies.map((policy) => (
                <AccordionItem key={policy.room_policy_id} value={policy.room_policy_id} className="rounded-2xl border border-slate-200 bg-white px-4">
                  <AccordionTrigger className="text-left">
                    <div>
                      <p className="font-medium text-slate-950">{policy.room_type}</p>
                      <p className="text-xs text-slate-500">{policy.room_policy_id}</p>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <form
                      className="space-y-3"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        const data = new FormData(event.currentTarget)
                        await updateRoomPolicy(policy.room_policy_id, {
                          speaker_mode: String(data.get("speaker_mode") || ""),
                          visible_participants: parseCommaList(String(data.get("visible_participants") || "")),
                          turn_taking_rule: String(data.get("turn_taking_rule") || ""),
                          escalation_rule: String(data.get("escalation_rule") || ""),
                        })
                      }}
                    >
                      <Input name="speaker_mode" defaultValue={policy.speaker_mode} placeholder="speaker mode" />
                      <Input
                        name="visible_participants"
                        defaultValue={(policy.visible_participants || []).join(",")}
                        placeholder="visible participants"
                      />
                      <Input name="turn_taking_rule" defaultValue={policy.turn_taking_rule} placeholder="turn taking rule" />
                      <Input name="escalation_rule" defaultValue={policy.escalation_rule} placeholder="escalation rule" />
                      <Button type="submit" className="w-full">
                        <Save className="h-4 w-4" />
                        Save Room Policy
                      </Button>
                    </form>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardDescription>Native Runtime Controls</CardDescription>
            <CardTitle>OpenClaw Config + Hook Editor</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => void syncOpenClawProvision()}>
                Sync Runtime Home
              </Button>
            </div>
            <Accordion type="multiple" className="space-y-4">
              {collections.openclawBindings.map((binding) => (
                <AccordionItem key={binding.employee_id} value={binding.employee_id} className="rounded-2xl border border-slate-200 bg-white px-4">
                  <AccordionTrigger className="text-left">
                    <div>
                      <p className="font-medium text-slate-950">{binding.employee_id}</p>
                      <p className="text-xs text-slate-500">{binding.openclaw_agent_id}</p>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <form
                      className="space-y-3"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        const data = new FormData(event.currentTarget)
                        await updateOpenClawBinding(binding.employee_id, {
                          tool_profile: String(data.get("tool_profile") || ""),
                          sandbox_profile: String(data.get("sandbox_profile") || ""),
                        })
                      }}
                    >
                      <Input name="tool_profile" defaultValue={binding.tool_profile} placeholder="tool profile" />
                      <Input name="sandbox_profile" defaultValue={binding.sandbox_profile} placeholder="sandbox profile" />
                      <Button type="submit" className="w-full">
                        <Save className="h-4 w-4" />
                        Save OpenClaw Binding
                      </Button>
                    </form>
                  </AccordionContent>
                </AccordionItem>
              ))}

              {(collections.openclawHooks?.entries || []).map((entry) => (
                <AccordionItem key={entry.hook_id} value={entry.hook_id} className="rounded-2xl border border-slate-200 bg-white px-4">
                  <AccordionTrigger className="text-left">
                    <div>
                      <p className="font-medium text-slate-950">{entry.hook_id}</p>
                      <p className="text-xs text-slate-500">{entry.source}</p>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent>
                    <form
                      className="space-y-3"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        const data = new FormData(event.currentTarget)
                        await updateOpenClawHook(entry.hook_id, {
                          enabled: String(data.get("enabled")) === "true",
                          config: JSON.parse(String(data.get("config") || "{}")),
                        })
                      }}
                    >
                      <Input name="enabled" defaultValue={entry.enabled ? "true" : "false"} placeholder="true / false" />
                      <Textarea name="config" rows={6} defaultValue={JSON.stringify(entry.config || {}, null, 2)} />
                      <Button type="submit" className="w-full">
                        <Save className="h-4 w-4" />
                        Save Hook Entry
                      </Button>
                    </form>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </CardContent>
        </Card>
      </div>

      <Card className="glass-panel">
        <CardHeader>
          <CardDescription>GitHub-sourced installed skills with license / install / verify metadata</CardDescription>
          <CardTitle>Core Bot Skill Catalog</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[1.2fr,0.8fr]">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {coreEmployeePacks.map((pack) => (
                <Card key={pack.employee_id} className="subtle-outline">
                  <CardContent className="space-y-3 p-4">
                    <div>
                      <p className="text-sm font-semibold text-slate-950">{pack.employee_name}</p>
                      <p className="text-xs text-slate-500">{pack.department}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                        <p className="text-slate-500">Professional</p>
                        <p className="mt-1 text-lg font-semibold text-slate-950">{pack.professional_skills?.length || 0}</p>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                        <p className="text-slate-500">General</p>
                        <p className="mt-1 text-lg font-semibold text-slate-950">{pack.general_skills?.length || 0}</p>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Sample Professional Skills</p>
                      <div className="space-y-1 text-sm text-slate-600">
                        {(pack.professional_skills || []).slice(0, 4).map((skill) => (
                          <div key={`${pack.employee_id}-${skill.skill_id}`} className="rounded-lg border border-slate-200 px-3 py-2">
                            <p className="font-medium text-slate-900">{skill.skill_name}</p>
                            <p className="text-xs text-slate-500">
                              {skill.source_ref.repo_name}:{skill.source_ref.path}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="space-y-4">
              <Card className="subtle-outline">
                <CardContent className="space-y-3 p-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Catalog Validation</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">
                      {validation?.ok ? "All Installed Skills Verified" : "Validation Issues Present"}
                    </p>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    <p>Employees covered: {coreEmployeePacks.length}</p>
                    <p>Issues: {validation?.issues.length || 0}</p>
                  </div>
                  <div className="space-y-2 text-sm text-slate-600">
                    {(validation?.issues || []).slice(0, 6).map((issue, index) => (
                      <div key={`${issue.skill_id || issue.employee_id || "issue"}-${index}`} className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2">
                        <p className="font-medium text-rose-700">{issue.issue_type}</p>
                        <p>{issue.detail}</p>
                      </div>
                    ))}
                    {!validation?.issues.length && <p>当前 7 个核心 bot 的 skill catalog 已通过本地验证。</p>}
                  </div>
                </CardContent>
              </Card>

              <Card className="subtle-outline">
                <CardContent className="space-y-3 p-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Recent Skill Invocations</p>
                    <p className="mt-2 text-lg font-semibold text-slate-950">Invocation Audit</p>
                  </div>
                  <div className="space-y-2 text-sm text-slate-600">
                    {collections.skillInvocations.slice(0, 8).map((record) => (
                      <div key={record.invocation_id} className="rounded-lg border border-slate-200 px-3 py-2">
                        <p className="font-medium text-slate-900">{record.employee_id}</p>
                        <p className="text-xs text-slate-500">{record.skill_id}</p>
                        <p className="mt-1">
                          {record.scope} · {record.status}
                        </p>
                      </div>
                    ))}
                    {!collections.skillInvocations.length && <p>当前还没有 skill invocation 记录。</p>}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
