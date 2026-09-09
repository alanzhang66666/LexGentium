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
    <Card className={cn(className)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className={cn("text-xl font-medium tracking-tight", trendColors[trend])}>{value}</p>
          </div>
          <Icon className="size-4 text-muted-foreground" />
        </div>
      </CardContent>
    </Card>
  )
}
