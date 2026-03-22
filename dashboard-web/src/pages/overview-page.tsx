import { Link } from "react-router-dom"
import { AlertTriangle, ArrowRight, Bot, LifeBuoy, Orbit, RefreshCcw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { MetricCard } from "@/components/shared/metric-card"
import { StatusBadge } from "@/components/shared/status-badge"
import { useDashboard, useOverviewMetrics, useStatusSummary } from "@/context/dashboard-context"
import { formatDateTime } from "@/lib/utils"

export function OverviewPage() {
  const { collections, isRefreshing, refreshAll, openControlUi } = useDashboard()
  const metrics = useOverviewMetrics()
  const summary = useStatusSummary()

  return (
    <div className="space-y-6 animate-fade-in">
      <section className="grid gap-4 lg:grid-cols-[1.45fr,0.95fr]">
        <Card className="glass-panel overflow-hidden">
          <CardContent className="grid gap-6 p-6 lg:grid-cols-[1.3fr,0.9fr]">
            <div className="space-y-4">
              <span className="inline-flex rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">
                White-tech operator console
              </span>
              <div className="space-y-3">
                <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-slate-950">
                  通过一个更清晰的控制台，管理 CEO 指令、Feishu 通信、OpenClaw 原生运行态与治理状态。
                </h1>
                <p className="max-w-2xl text-base leading-7 text-slate-600">
                  新 UI 不再堆叠长单页，而是按运营对象拆成多视图控制台。Overview 用来在 5 秒内扫到系统健康、dead letter、
                  native runs 与 control plane 的关键状态。
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button onClick={openControlUi}>
                  <LifeBuoy className="h-4 w-4" />
                  打开已配对 Control UI
                </Button>
                <Button variant="outline" onClick={() => void refreshAll()} disabled={isRefreshing}>
                  <RefreshCcw className="h-4 w-4" />
                  全局刷新
                </Button>
                <Button variant="ghost" asChild>
                  <Link to="/openclaw">
                    打开 OpenClaw Runtime
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button variant="ghost" asChild>
                  <Link to="/growth">
                    打开 Growth Ops
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>

            <div className="grid gap-3">
              <Card className="subtle-outline">
                <CardHeader className="pb-2">
                  <CardDescription>Gateway</CardDescription>
                  <CardTitle className="flex items-center justify-between text-lg">
                    <span>{collections.openclawGatewayHealth?.status || "unknown"}</span>
                    <StatusBadge value={summary.gatewayStatus} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-slate-600">
                  <p>Runtime mode: {summary.runtimeMode}</p>
                  <p>Ops issues: {summary.issueCount}</p>
                </CardContent>
              </Card>
              <Card className="subtle-outline">
                <CardHeader className="pb-2">
                  <CardDescription>Feishu Error Queue</CardDescription>
                  <CardTitle className="flex items-center justify-between text-lg">
                    <span>{collections.feishuDeadLetters.length}</span>
                    <StatusBadge value={collections.feishuDeadLetters.length ? "warning" : "healthy"} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-slate-600">
                  <p>Replay audit: {collections.feishuReplayAudit.length}</p>
                  <p>Bots online: {collections.feishuBots.length}</p>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
          {metrics.map((metric, index) => (
            <MetricCard
              key={metric.label}
              label={metric.label}
              value={metric.value}
              eyebrow={index === 0 ? "Live summary" : undefined}
              accent={index === 2 && metric.value !== 0}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr,0.9fr]">
        <Card className="glass-panel">
          <CardHeader>
            <CardDescription>Recent Native Runs</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Orbit className="h-4 w-4 text-cyan-600" />
              最新 OpenClaw 运行
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {collections.openclawRecentRuns.slice(0, 5).map((run) => (
              <article key={run.runtrace_id} className="rounded-2xl border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-950">{run.work_ticket_ref}</p>
                    <p className="mt-1 text-sm text-slate-500">{run.model_ref}</p>
                  </div>
                  <StatusBadge value={run.strategy} />
                </div>
                <Separator className="my-3" />
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>{run.surface}</span>
                  <span>{formatDateTime(run.last_event_at)}</span>
                </div>
              </article>
            ))}
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardDescription>Dead Letter Queue</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-amber-500" />
              Feishu Error Queue
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {collections.feishuDeadLetters.slice(0, 5).map((item) => (
              <article key={item.outbound_id} className="rounded-2xl border border-rose-100 bg-rose-50/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-slate-950">{item.source_kind}</p>
                    <p className="mt-1 line-clamp-2 text-sm text-slate-600">{item.text}</p>
                  </div>
                  <StatusBadge value={item.status} />
                </div>
                <p className="mt-3 text-xs text-rose-700">{item.error_detail || "待重放"}</p>
              </article>
            ))}
          </CardContent>
        </Card>

        <Card className="glass-panel">
          <CardHeader>
            <CardDescription>Ops Alerts</CardDescription>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              当前需关注事项
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {collections.openclawIssues.length ? (
              collections.openclawIssues.slice(0, 6).map((issue, index) => (
                <article key={`${issue.issue_id || issue.summary || issue.message || index}`} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-slate-950">{issue.summary || issue.message || "OpenClaw ops issue"}</p>
                    <StatusBadge value={issue.severity || "warning"} />
                  </div>
                </article>
              ))
            ) : (
              <div className="rounded-2xl border border-emerald-100 bg-emerald-50/80 px-4 py-10 text-center text-sm text-emerald-700">
                当前没有新的 Gateway / Runtime 阻塞级告警。
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}
