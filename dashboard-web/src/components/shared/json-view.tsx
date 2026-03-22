import { ScrollArea } from "@/components/ui/scroll-area"
import { safeJson } from "@/lib/utils"

export function JsonView({ value, empty = "暂无数据" }: { value: unknown; empty?: string }) {
  if (!value) {
    return <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-sm text-slate-500">{empty}</div>
  }

  return (
    <ScrollArea className="h-[320px] rounded-2xl border border-slate-200 bg-slate-950/95 p-4">
      <pre className="font-mono text-xs leading-6 text-slate-100">{safeJson(value)}</pre>
    </ScrollArea>
  )
}
