import { useMemo } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { Bot, House, LifeBuoy, MessageSquareText, Orbit, Rocket, Settings2, Ticket, UserRoundCog, Workflow } from "lucide-react"

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command"
import { useDashboard } from "@/context/dashboard-context"

const navigationItems = [
  { to: "/", label: "Overview", icon: House },
  { to: "/control-plane", label: "Control Plane", icon: Workflow },
  { to: "/growth", label: "Growth Ops", icon: Rocket },
  { to: "/conversations", label: "Conversations", icon: MessageSquareText },
  { to: "/feishu", label: "Feishu Ops", icon: Bot },
  { to: "/agents", label: "Agents", icon: UserRoundCog },
  { to: "/openclaw", label: "OpenClaw Runtime", icon: Orbit },
  { to: "/settings", label: "Settings", icon: Settings2 },
]

export function AppCommandBar({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const location = useLocation()
  const { collections, openControlUi, selectTicket, selectThread, selectOpenClawRun } = useDashboard()

  const searchBuckets = useMemo(
    () => ({
      tickets: collections.tickets.slice(-6).reverse(),
      threads: collections.threads.slice(-6).reverse(),
      runs: collections.openclawRecentRuns.slice(0, 6),
    }),
    [collections]
  )

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="跳转视图、打开工单、查看最近 native run..." />
      <CommandList>
        <CommandEmpty>没有匹配结果。</CommandEmpty>
        <CommandGroup heading="Navigation">
          {navigationItems.map((item) => {
            const Icon = item.icon
            return (
              <CommandItem
                key={item.to}
                value={`${item.label} ${item.to}`}
                onSelect={() => {
                  navigate(item.to)
                  onOpenChange(false)
                }}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
                {location.pathname === item.to ? <CommandShortcut>Current</CommandShortcut> : null}
              </CommandItem>
            )
          })}
          <CommandItem
            value="openclaw control ui launch"
            onSelect={() => {
              openControlUi()
              onOpenChange(false)
            }}
          >
            <LifeBuoy className="h-4 w-4" />
            <span>Open Ready Control UI</span>
          </CommandItem>
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Recent Tickets">
          {searchBuckets.tickets.map((ticket) => (
            <CommandItem
              key={ticket.ticket_id}
              value={`${ticket.title} ${ticket.ticket_id} ${ticket.status}`}
              onSelect={async () => {
                navigate("/control-plane")
                await selectTicket(ticket.ticket_id)
                onOpenChange(false)
              }}
            >
              <Ticket className="h-4 w-4" />
              <span>{ticket.title}</span>
              <CommandShortcut>{ticket.status}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Recent Threads">
          {searchBuckets.threads.map((thread) => (
            <CommandItem
              key={thread.thread_id}
              value={`${thread.title} ${thread.thread_id} ${thread.surface}`}
              onSelect={async () => {
                navigate("/conversations")
                await selectThread(thread.thread_id)
                onOpenChange(false)
              }}
            >
              <MessageSquareText className="h-4 w-4" />
              <span>{thread.title}</span>
              <CommandShortcut>{thread.surface}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandSeparator />
        <CommandGroup heading="Recent Native Runs">
          {searchBuckets.runs.map((run) => (
            <CommandItem
              key={run.runtrace_id}
              value={`${run.runtrace_id} ${run.model_ref} ${run.strategy}`}
              onSelect={async () => {
                navigate("/openclaw")
                await selectOpenClawRun(run.runtrace_id)
                onOpenChange(false)
              }}
            >
              <Orbit className="h-4 w-4" />
              <span>{run.work_ticket_ref}</span>
              <CommandShortcut>{run.strategy}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  )
}
