import { Command, LifeBuoy, RefreshCcw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/shared/status-badge"
import { useDashboard, useStatusSummary } from "@/context/dashboard-context"

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const { config, refreshAll, isRefreshing, openControlUi } = useDashboard()
  const summary = useStatusSummary()

  return (
    <header className="sticky top-0 z-40 border-b border-white/70 bg-white/80 backdrop-blur-xl">
      <div className="flex flex-col gap-4 px-5 py-4 lg:px-8 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">OpenClaw Native Agent Plane</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">CEO Dashboard</h2>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge value={summary.gatewayStatus} />
          <StatusBadge value={summary.runtimeMode} />
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            Env · {config.appEnv}
          </span>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            Issues · {summary.issueCount}
          </span>
          <Button variant="outline" size="sm" onClick={onOpenCommand}>
            <Command className="h-4 w-4" />
            Command
          </Button>
          <Button variant="outline" size="sm" onClick={() => void refreshAll()} disabled={isRefreshing}>
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </Button>
          <Button size="sm" onClick={openControlUi}>
            <LifeBuoy className="h-4 w-4" />
            Open Control UI
          </Button>
        </div>
      </div>
    </header>
  )
}
