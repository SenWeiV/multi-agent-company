import { NavLink } from "react-router-dom"
import { Bot, House, MessageSquareText, Orbit, Rocket, Settings2, UserRoundCog, Workflow } from "lucide-react"

import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

const items = [
  { to: "/", label: "Overview", icon: House },
  { to: "/control-plane", label: "Control Plane", icon: Workflow },
  { to: "/growth", label: "Growth Ops", icon: Rocket },
  { to: "/conversations", label: "Conversations", icon: MessageSquareText },
  { to: "/feishu", label: "Feishu Ops", icon: Bot },
  { to: "/agents", label: "Agents", icon: UserRoundCog },
  { to: "/openclaw", label: "OpenClaw Runtime", icon: Orbit },
  { to: "/settings", label: "Settings", icon: Settings2 },
]

export function AppSidebar() {
  return (
    <aside className="hidden w-[280px] shrink-0 border-r border-slate-200/80 bg-white/80 xl:flex">
      <ScrollArea className="flex-1">
        <div className="surface-grid min-h-screen px-5 py-6">
          <div className="rounded-3xl border border-cyan-100 bg-gradient-to-br from-cyan-50 to-white p-5 shadow-lift">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-700">One-Person Company</p>
            <h1 className="mt-3 text-xl font-semibold tracking-tight text-slate-950">Control Center</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              OpenClaw、Feishu 与 company control plane 的统一运营面。
            </p>
          </div>

          <nav className="mt-8 space-y-2">
            {items.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "group flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium text-slate-600 transition-all hover:bg-slate-100 hover:text-slate-950",
                      isActive && "bg-slate-950 text-white shadow-panel"
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </nav>
        </div>
      </ScrollArea>
    </aside>
  )
}
