import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { Toaster } from "sonner"

import { AppShell } from "@/components/layout/app-shell"
import { DashboardProvider } from "@/context/dashboard-context"
import { AgentsPage } from "@/pages/agents-page"
import { ControlPlanePage } from "@/pages/control-plane-page"
import { ConversationsPage } from "@/pages/conversations-page"
import { FeishuOpsPage } from "@/pages/feishu-ops-page"
import { GrowthOpsPage } from "@/pages/growth-ops-page"
import { OpenClawRuntimePage } from "@/pages/openclaw-runtime-page"
import { OverviewPage } from "@/pages/overview-page"
import { SettingsPage } from "@/pages/settings-page"

function App() {
  return (
    <BrowserRouter basename="/dashboard">
      <DashboardProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="control-plane" element={<ControlPlanePage />} />
            <Route path="growth" element={<GrowthOpsPage />} />
            <Route path="conversations" element={<ConversationsPage />} />
            <Route path="feishu" element={<FeishuOpsPage />} />
            <Route path="openclaw" element={<OpenClawRuntimePage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
        <Toaster richColors position="top-right" />
      </DashboardProvider>
    </BrowserRouter>
  )
}

export default App
