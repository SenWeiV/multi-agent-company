import { Badge } from "@/components/ui/badge"
import { cn, statusTone } from "@/lib/utils"

const toneClasses = {
  default: "bg-slate-100 text-slate-700 hover:bg-slate-100",
  success: "bg-emerald-100 text-emerald-700 hover:bg-emerald-100",
  warning: "bg-amber-100 text-amber-800 hover:bg-amber-100",
  destructive: "bg-rose-100 text-rose-700 hover:bg-rose-100",
} as const

export function StatusBadge({ value, className }: { value?: string | null; className?: string }) {
  const tone = statusTone(value)
  return (
    <Badge variant="secondary" className={cn("border-transparent", toneClasses[tone], className)}>
      {value || "n/a"}
    </Badge>
  )
}
