import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

export function MetricCard({
  label,
  value,
  eyebrow,
  accent = false,
}: {
  label: string
  value: string | number
  eyebrow?: string
  accent?: boolean
}) {
  return (
    <Card className={cn("glass-panel", accent && "ring-1 ring-cyan-200/80")}>
      <CardHeader className="space-y-3 pb-3">
        {eyebrow ? <Badge variant="secondary" className="w-fit rounded-full bg-cyan-50 text-cyan-700">{eyebrow}</Badge> : null}
        <CardTitle className="text-sm font-medium text-slate-500">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tracking-tight text-slate-950">{value}</div>
      </CardContent>
    </Card>
  )
}
