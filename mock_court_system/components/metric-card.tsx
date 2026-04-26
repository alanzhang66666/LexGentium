import type { LucideIcon } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface MetricCardProps {
  icon: LucideIcon
  label: string
  value: string
  trend?: "up" | "down" | "neutral"
  className?: string
}

export function MetricCard({ icon: Icon, label, value, trend = "neutral", className }: MetricCardProps) {
  const trendColors = {
    up: "text-accent",
    down: "text-destructive",
    neutral: "text-muted-foreground",
  }

  return (
    <Card className={cn("border-2 hover:shadow-lg transition-all group", className)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
            <p className={cn("text-2xl font-bold tracking-tight", trendColors[trend])}>{value}</p>
          </div>
          <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-br from-primary/10 to-primary/5 group-hover:from-primary/20 group-hover:to-primary/10 transition-colors">
            <Icon className="w-6 h-6 text-primary" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
