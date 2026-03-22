import type { ComponentProps } from "react"

import { GripVertical } from "lucide-react"
import { Group, Panel, Separator } from "react-resizable-panels"

import { cn } from "@/lib/utils"

function ResizablePanelGroup({
  className,
  ...props
}: ComponentProps<"div"> & { direction?: "horizontal" | "vertical"; autoSaveId?: string }) {
  return (
    <Group
      className={cn("flex h-full w-full data-[group-direction=vertical]:flex-col", className)}
      {...(props as Record<string, unknown>)}
    />
  )
}

const ResizablePanel = Panel

function ResizableHandle({
  className,
  withHandle,
  ...props
}: ComponentProps<typeof Separator> & { withHandle?: boolean }) {
  return (
    <Separator
      className={cn(
        "relative flex w-px items-center justify-center bg-slate-200 after:absolute after:inset-y-0 after:left-1/2 after:w-4 after:-translate-x-1/2 data-[group-direction=vertical]:h-px data-[group-direction=vertical]:w-full",
        className
      )}
      {...props}
    >
      {withHandle ? (
        <div className="z-10 rounded-full border border-slate-200 bg-white p-1 text-slate-400 shadow-sm">
          <GripVertical className="h-3.5 w-3.5" />
        </div>
      ) : null}
    </Separator>
  )
}

export { ResizableHandle, ResizablePanel, ResizablePanelGroup }
