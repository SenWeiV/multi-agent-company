import { useEffect, useState } from "react"
import { Outlet } from "react-router-dom"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AppSidebar } from "@/components/layout/app-sidebar"
import { Topbar } from "@/components/layout/topbar"
import { AppCommandBar } from "@/components/shared/app-command-bar"
import { useDashboard } from "@/context/dashboard-context"

export function AppShell() {
  const { notice } = useDashboard()
  const [commandOpen, setCommandOpen] = useState(false)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault()
        setCommandOpen((current) => !current)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  return (
    <div className="min-h-screen xl:flex">
      <AppSidebar />
      <div className="min-w-0 flex-1">
        <Topbar onOpenCommand={() => setCommandOpen(true)} />
        <main className="px-4 py-6 lg:px-8">
          {notice ? (
            <Alert className="mb-6 border-slate-200 bg-white/70">
              <AlertTitle>{notice.message}</AlertTitle>
              {notice.detail ? <AlertDescription>{notice.detail}</AlertDescription> : null}
            </Alert>
          ) : null}
          <Outlet />
        </main>
      </div>
      <AppCommandBar open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  )
}
